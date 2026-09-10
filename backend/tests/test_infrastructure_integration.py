from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.infrastructure.postgres import PostgresPositionRepository, create_postgres_pool
from app.infrastructure.valkey import ValkeyLivePositionCache, create_valkey_client
from app.modules.mobility.models import VehiclePosition

pytestmark = pytest.mark.integration

DATABASE_URL = os.getenv("TEST_DATABASE_URL")
CACHE_URL = os.getenv("TEST_CACHE_URL")


def _require_integration_env() -> tuple[str, str]:
    if not DATABASE_URL or not CACHE_URL:
        pytest.skip("integration infrastructure URLs are not configured")
    return DATABASE_URL, CACHE_URL


async def _reset_and_migrate(pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute("DROP SCHEMA IF EXISTS transit CASCADE")
        await conn.execute("DROP TABLE IF EXISTS public.schema_migrations")
        migrations_dir = Path(__file__).resolve().parents[1] / "app" / "migrations"
        for migration in sorted(migrations_dir.glob("*.sql")):
            async with conn.transaction():
                await conn.execute(migration.read_text(encoding="utf-8"))


@pytest.mark.asyncio
async def test_postgis_repository_is_idempotent_and_supports_nearby_query() -> None:
    database_url, _ = _require_integration_env()
    pool = await create_postgres_pool(database_url)
    try:
        await _reset_and_migrate(pool)
        repository = PostgresPositionRepository(pool)
        # Anchor the fixture at the start of a second. Replacing a random current
        # microsecond with 500000 could otherwise move the supposed newer sample
        # backwards and make this contract test depend on runner timing.
        now = datetime.now(UTC).replace(microsecond=0)
        position = VehiclePosition(
            agency_id="br-rj-rio-smtr-sppo",
            vehicle_id="D12345",
            route_id="457",
            latitude=-22.912345,
            longitude=-43.203456,
            speed_mps=7.5,
            observed_at=now,
            received_at=now,
            source="integration-test",
        )

        assert await repository.save_many([position]) == 1
        assert await repository.save_many([position]) == 0

        nearby = await repository.nearby(
            latitude=-22.912345,
            longitude=-43.203456,
            radius_m=100,
            max_age_seconds=300,
            limit=10,
        )
        assert len(nearby) == 1
        assert nearby[0].vehicle_id == "D12345"
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_valkey_cache_and_distributed_lease_contract() -> None:
    _, cache_url = _require_integration_env()
    client = await create_valkey_client(cache_url)
    try:
        await client.flushdb()
        cache = ValkeyLivePositionCache(client, ttl_seconds=180)
        now = datetime.now(UTC)
        position = VehiclePosition(
            agency_id="br-rj-rio-smtr-sppo",
            vehicle_id="D12345",
            route_id="457",
            latitude=-22.912345,
            longitude=-43.203456,
            observed_at=now,
            received_at=now,
            source="integration-test",
        )

        assert await cache.put_many([position]) == 1
        by_route = await cache.by_route(
            agency_id="br-rj-rio-smtr-sppo",
            route_id="457",
        )
        assert [item.vehicle_id for item in by_route] == ["D12345"]

        newer = position.model_copy(
            update={
                "latitude": -22.91,
                "observed_at": now.replace(microsecond=500000),
                "received_at": now.replace(microsecond=500000),
            }
        )
        older = position.model_copy(
            update={
                "latitude": -22.99,
                "observed_at": now.replace(microsecond=100000),
                "received_at": now.replace(microsecond=600000),
            }
        )
        assert await cache.put_many([newer]) == 1
        assert await cache.put_many([older]) == 0
        latest = await cache.by_route(agency_id="br-rj-rio-smtr-sppo", route_id="457")
        assert latest[0].latitude == pytest.approx(-22.91)

        assert await cache.try_acquire(name="integration", token="owner-a", ttl_ms=10_000)
        assert not await cache.try_acquire(name="integration", token="owner-b", ttl_ms=10_000)
        await cache.release(name="integration", token="owner-b")
        assert not await cache.try_acquire(name="integration", token="owner-b", ttl_ms=10_000)
        await cache.release(name="integration", token="owner-a")
        assert await cache.try_acquire(name="integration", token="owner-b", ttl_ms=10_000)
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_postgres_to_verified_parquet_archive_pipeline(tmp_path: Path) -> None:
    from datetime import date

    from app.infrastructure.parquet import LocalParquetArchiveWriter
    from app.infrastructure.postgres import (
        PostgresArchiveManifestCatalog,
        PostgresHistoricalPositionSource,
        PostgresHotPartitionRepository,
    )
    from app.modules.mobility.archive.service import ArchiveDayService

    database_url, _ = _require_integration_env()
    pool = await create_postgres_pool(database_url)
    try:
        await _reset_and_migrate(pool)
        repository = PostgresPositionRepository(pool)
        archive_day = date(2026, 9, 1)
        positions = []
        for index in range(3):
            timestamp = datetime(2026, 9, 1, 12, index, tzinfo=UTC)
            positions.append(
                VehiclePosition(
                    agency_id="br-rj-rio-smtr-sppo",
                    vehicle_id=f"D{index:05d}",
                    route_id="457",
                    latitude=-22.91 + index * 0.001,
                    longitude=-43.20,
                    observed_at=timestamp,
                    received_at=timestamp,
                    source="rio-smtr-gps",
                )
            )
        assert await repository.save_many(positions) == 3

        catalog = PostgresArchiveManifestCatalog(pool)
        service = ArchiveDayService(
            source="rio-smtr-gps",
            historical_source=PostgresHistoricalPositionSource(pool),
            writer=LocalParquetArchiveWriter(tmp_path),
            catalog=catalog,
            batch_size=2,
        )
        report = await service.run_day(day=archive_day)

        assert report.status == "verified"
        assert report.row_count == 3
        assert report.object_uri is not None
        assert await catalog.is_verified(source="rio-smtr-gps", day=archive_day)
        manifest = await catalog.get_verified(source="rio-smtr-gps", day=archive_day)
        assert manifest is not None
        assert manifest.row_count == 3
        assert manifest.sha256 == report.sha256

        hot = PostgresHotPartitionRepository(pool)
        assert await hot.source_row_count(day=archive_day, source="rio-smtr-gps") == 3
        assert not await hot.contains_other_sources(day=archive_day, source="rio-smtr-gps")
        assert not await hot.drop_partition_if_unchanged(
            day=archive_day, source="rio-smtr-gps", expected_row_count=2
        )
        assert await hot.drop_partition_if_unchanged(
            day=archive_day, source="rio-smtr-gps", expected_row_count=3
        )
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_operational_repository_reads_ingestion_evidence() -> None:
    from app.infrastructure.postgres import PostgresOperationalRepository

    database_url, _ = _require_integration_env()
    pool = await create_postgres_pool(database_url)
    try:
        await _reset_and_migrate(pool)
        now = datetime.now(UTC)
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO transit.ingestion_runs (
                    source, status, started_at, finished_at, received_records, rejected_records,
                    deduplicated_records, persisted_records, cached_records, quality_counts,
                    contract_fingerprint, observed_fields
                ) VALUES (
                    'rio-smtr-gps','success',$1,$2,100,1,2,97,97,'{"good":97}'::jsonb,
                    'fingerprint-a','["id_veiculo"]'::jsonb
                )
                """,
                now,
                now,
            )
        repository = PostgresOperationalRepository(pool)
        runs = await repository.ingestion_runs_since(
            source="rio-smtr-gps",
            since=now.replace(hour=0, minute=0, second=0, microsecond=0),
        )
        assert len(runs) == 1
        assert runs[0].received_records == 100
        assert runs[0].rejected_records == 1
        assert runs[0].contract_fingerprint == "fingerprint-a"
    finally:
        await pool.close()
