from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

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


def _write_minimal_gtfs(path: Path) -> None:
    files = {
        "agency.txt": (
            "agency_id,agency_name,agency_url,agency_timezone\n"
            "RIO,SMTR,https://transportes.prefeitura.rio,America/Sao_Paulo\n"
        ),
        "routes.txt": (
            "route_id,agency_id,route_short_name,route_long_name,route_type\n"
            "483,RIO,483,Penha - General Osorio,3\n"
        ),
        "stops.txt": (
            "stop_id,stop_name,stop_lat,stop_lon\n"
            "S1,Start,-22.9,-43.2\n"
            "S2,Central,-22.9,-43.199\n"
            "S3,End,-22.9,-43.198\n"
        ),
        "trips.txt": "route_id,service_id,trip_id,shape_id\n483,WK,T1,SH1\n",
        "stop_times.txt": (
            "trip_id,arrival_time,departure_time,stop_id,stop_sequence,"
            "shape_dist_traveled\n"
            "T1,12:00:00,12:00:00,S1,1,0\n"
            "T1,12:01:00,12:01:00,S2,2,100\n"
            "T1,12:02:00,12:02:00,S3,3,200\n"
        ),
        "calendar_dates.txt": "service_id,date,exception_type\nWK,20260912,1\n",
        "shapes.txt": (
            "shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence,"
            "shape_dist_traveled\n"
            "SH1,-22.9,-43.2,1,0\n"
            "SH1,-22.9,-43.199,2,100\n"
            "SH1,-22.9,-43.198,3,200\n"
        ),
    }
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        for filename, content in files.items():
            archive.writestr(filename, content)


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
            shape_id="SH1",
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
        assert nearby[0].shape_id == "SH1"
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_gtfs_stop_distance_rehydration_uses_real_postgres(tmp_path: Path) -> None:
    from app.modules.mobility.gtfs.importer import PostgresGtfsImporter
    from app.modules.mobility.gtfs.validator import validate_gtfs_snapshot

    database_url, _ = _require_integration_env()
    pool = await create_postgres_pool(database_url, command_timeout=None)
    try:
        await _reset_and_migrate(pool)
        path = tmp_path / "gtfs.zip"
        _write_minimal_gtfs(path)
        manifest = validate_gtfs_snapshot(
            path,
            source_url="https://dados.mobilidade.rio/gtfs/schedule",
        )
        importer = PostgresGtfsImporter(pool)
        await importer.import_snapshot(path, manifest)
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE transit.gtfs_stop_times SET shape_dist_traveled = NULL"
            )

        result = await importer.rehydrate_stop_distances(path, manifest)

        assert result.updated_rows == 3
        assert result.target_non_null_rows == 3
        async with pool.acquire() as conn:
            values = await conn.fetch(
                "SELECT shape_dist_traveled FROM transit.gtfs_stop_times "
                "ORDER BY stop_sequence"
            )
        assert [row["shape_dist_traveled"] for row in values] == pytest.approx([0, 100, 200])
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_vehicle_is_projected_to_shape_and_upcoming_stops(tmp_path: Path) -> None:
    from app.infrastructure.gtfs_postgres import PostgresGtfsCatalog
    from app.modules.mobility.gtfs.importer import PostgresGtfsImporter
    from app.modules.mobility.gtfs.models import EtaMethod, JourneyMatchMethod
    from app.modules.mobility.gtfs.validator import validate_gtfs_snapshot

    database_url, _ = _require_integration_env()
    pool = await create_postgres_pool(database_url, command_timeout=None)
    try:
        await _reset_and_migrate(pool)
        path = tmp_path / "gtfs.zip"
        _write_minimal_gtfs(path)
        manifest = validate_gtfs_snapshot(
            path,
            source_url="https://dados.mobilidade.rio/gtfs/schedule",
        )
        await PostgresGtfsImporter(pool).import_snapshot(path, manifest)
        observed_at = datetime.now(UTC).replace(microsecond=0)
        positions = tuple(
            VehiclePosition(
                agency_id="br-rj-rio-smtr-sppo",
                vehicle_id="D12345",
                route_id="483",
                trip_id="T1",
                shape_id="SH1",
                latitude=-22.9,
                longitude=-43.1994,
                speed_mps=speed,
                observed_at=observed_at - timedelta(seconds=seconds_ago),
                received_at=observed_at - timedelta(seconds=seconds_ago),
                source="integration-test",
            )
            for seconds_ago, speed in ((120, 4.0), (60, 5.0), (0, 6.0))
        )
        await PostgresPositionRepository(pool).save_many(positions)
        position = positions[-1]

        result = await PostgresGtfsCatalog(pool).match_vehicle_to_upcoming_stops(
            position=position,
            limit=2,
            max_projection_distance_m=250,
        )

        assert result.available is True
        assert result.match_method is JourneyMatchMethod.EXACT_TRIP
        assert result.projection_distance_m == pytest.approx(0, abs=0.1)
        assert result.projected_shape_dist_traveled == pytest.approx(60, abs=0.1)
        assert [stop.stop_id for stop in result.upcoming_stops] == ["S2", "S3"]
        assert result.upcoming_stops[0].shape_distance_ahead == pytest.approx(40, abs=0.1)
        assert result.eta_evidence is not None
        assert result.eta_evidence.method is EtaMethod.VEHICLE_RECENT_SPEED
        assert result.eta_evidence.sample_count == 3
        assert result.eta_evidence.speed_median_mps == pytest.approx(5)
        assert result.upcoming_stops[0].eta_seconds is not None
        assert result.upcoming_stops[0].eta_upper_seconds is not None
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_eta_uses_historical_segment_time_band_as_bounded_fallback(
    tmp_path: Path,
) -> None:
    from app.infrastructure.gtfs_postgres import PostgresGtfsCatalog
    from app.modules.mobility.gtfs.importer import PostgresGtfsImporter
    from app.modules.mobility.gtfs.models import EtaMethod
    from app.modules.mobility.gtfs.validator import validate_gtfs_snapshot

    database_url, _ = _require_integration_env()
    pool = await create_postgres_pool(database_url, command_timeout=None)
    try:
        await _reset_and_migrate(pool)
        path = tmp_path / "gtfs.zip"
        _write_minimal_gtfs(path)
        manifest = validate_gtfs_snapshot(
            path,
            source_url="https://dados.mobilidade.rio/gtfs/schedule",
        )
        await PostgresGtfsImporter(pool).import_snapshot(path, manifest)
        observed_at = datetime.now(UTC).replace(microsecond=0)
        positions = tuple(
            VehiclePosition(
                agency_id="br-rj-rio-smtr-sppo",
                vehicle_id="D12345",
                route_id="483",
                trip_id="T1",
                shape_id="SH1",
                latitude=-22.9,
                longitude=-43.1994,
                speed_mps=speed,
                observed_at=observed_at - timedelta(seconds=seconds_ago),
                received_at=observed_at - timedelta(seconds=seconds_ago),
                source="integration-test",
            )
            for seconds_ago, speed in ((60, 7.0), (0, 8.0))
        )
        await PostgresPositionRepository(pool).save_many(positions)
        async with pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO transit.eta_segment_speed_profiles (
                    window_start, window_end, route_id, latitude_cell,
                    longitude_cell, local_time_band, sample_count,
                    speed_p25_mps, speed_median_mps, speed_p75_mps
                )
                VALUES (
                    $1, $1::timestamptz + interval '15 minutes', '483',
                    floor((-22.9 + 90.0) / 0.0025)::integer,
                    floor((-43.1994 + 180.0) / 0.0025)::integer,
                    floor(extract(epoch FROM (
                        $1::timestamptz AT TIME ZONE 'America/Sao_Paulo'
                    )::time) / 900)::smallint,
                    30, 2.0, 3.0, 4.0
                )
                """,
                [
                    (observed_at - timedelta(days=1, minutes=15),),
                    (observed_at - timedelta(days=2, minutes=15),),
                ],
            )

        result = await PostgresGtfsCatalog(pool).match_vehicle_to_upcoming_stops(
            position=positions[-1],
            limit=2,
            max_projection_distance_m=250,
        )

        assert result.eta_evidence is not None
        assert result.eta_evidence.method is EtaMethod.HISTORICAL_SEGMENT_TIME_BAND
        assert result.eta_evidence.sample_count == 60
        assert result.eta_evidence.speed_median_mps == pytest.approx(3)
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_eta_segment_profile_refresh_aggregates_completed_window() -> None:
    from scripts.refresh_eta_segment_profiles import refresh_profiles

    database_url, _ = _require_integration_env()
    pool = await create_postgres_pool(database_url, command_timeout=None)
    try:
        await _reset_and_migrate(pool)
        now = datetime.now(UTC).replace(microsecond=0)
        positions = tuple(
            VehiclePosition(
                agency_id="br-rj-rio-smtr-sppo",
                vehicle_id=f"D{index}",
                route_id="483",
                latitude=-22.9,
                longitude=-43.2,
                speed_mps=speed,
                observed_at=now - timedelta(minutes=20, seconds=index),
                received_at=now - timedelta(minutes=20, seconds=index),
                source="integration-test",
            )
            for index, speed in enumerate((2.0, 4.0, 6.0))
        )
        await PostgresPositionRepository(pool).save_many(positions)
        async with pool.acquire() as conn, conn.transaction():
            profile_count = await refresh_profiles(
                conn,
                start=now - timedelta(hours=1),
                end=now - timedelta(minutes=5),
            )
            profile = await conn.fetchrow(
                """
                SELECT sample_count, speed_p25_mps, speed_median_mps, speed_p75_mps
                FROM transit.eta_segment_speed_profiles
                """
            )

        assert profile_count == 1
        assert profile["sample_count"] == 3
        assert profile["speed_p25_mps"] == pytest.approx(3)
        assert profile["speed_median_mps"] == pytest.approx(4)
        assert profile["speed_p75_mps"] == pytest.approx(5)
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_eta_replay_compares_prediction_with_future_gps(tmp_path: Path) -> None:
    from argparse import Namespace

    from app.modules.mobility.gtfs.importer import PostgresGtfsImporter
    from app.modules.mobility.gtfs.validator import validate_gtfs_snapshot
    from scripts.evaluate_eta_replay import _run

    database_url, _ = _require_integration_env()
    pool = await create_postgres_pool(database_url, command_timeout=None)
    try:
        await _reset_and_migrate(pool)
        path = tmp_path / "gtfs.zip"
        _write_minimal_gtfs(path)
        manifest = validate_gtfs_snapshot(
            path,
            source_url="https://dados.mobilidade.rio/gtfs/schedule",
        )
        await PostgresGtfsImporter(pool).import_snapshot(path, manifest)
        anchor = datetime.now(UTC).replace(microsecond=0) - timedelta(minutes=20)
        positions = tuple(
            VehiclePosition(
                agency_id="br-rj-rio-smtr-sppo",
                vehicle_id="D12345",
                route_id="483",
                trip_id="T1",
                shape_id="SH1",
                latitude=-22.9,
                longitude=longitude,
                speed_mps=speed,
                observed_at=observed_at,
                received_at=observed_at,
                source="integration-test",
            )
            for observed_at, longitude, speed in (
                (anchor - timedelta(seconds=120), -43.2, 4.0),
                (anchor - timedelta(seconds=60), -43.19995, 5.0),
                (anchor, -43.1999, 6.0),
                (anchor + timedelta(seconds=120), -43.199, 3.0),
            )
        )
        await PostgresPositionRepository(pool).save_many(positions)

        report = await _run(
            Namespace(
                anchor_age_minutes=20,
                anchor_window_seconds=60,
                outcome_horizon_minutes=10,
                stop_radius_m=30.0,
                max_samples=10,
                min_outcomes=1,
            ),
            database_url=database_url,
        )

        assert report["status"] == "sufficient_data"
        assert report["anchor_count"] == 1
        assert report["outcome_count"] == 1
        assert report["mae_seconds"] is not None
        assert report["mae_seconds"] > 60
        assert report["error_p50_seconds"] == report["mae_seconds"]
        assert report["methods"] == {"vehicle_recent_speed": 1}
        assert report["match_methods"] == {"exact_trip": 1}
        assert report["diagnostics"]["overall"]["outcome_count"] == 1
        assert report["diagnostics"]["by_eta_method"]["vehicle_recent_speed"][
            "outcome_count"
        ] == 1
        assert report["diagnostics"]["top_routes"][0]["route_id"] == "483"
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
                "observed_at": now + timedelta(seconds=1),
                "received_at": now + timedelta(seconds=1),
            }
        )
        older = position.model_copy(
            update={
                "latitude": -22.99,
                "observed_at": now - timedelta(seconds=1),
                "received_at": now + timedelta(seconds=2),
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
