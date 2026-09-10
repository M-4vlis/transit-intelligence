from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from typing import Any

from app.modules.mobility.models import RejectedSourceRecord, VehiclePosition


async def create_postgres_pool(
    dsn: str,
    *,
    command_timeout: float | None = 10,
) -> Any:
    import asyncpg

    return await asyncpg.create_pool(
        dsn=dsn,
        min_size=1,
        max_size=8,
        command_timeout=command_timeout,
    )


class PostgresPositionRepository:
    def __init__(self, pool: Any) -> None:
        self.pool = pool

    async def ping(self) -> bool:
        async with self.pool.acquire() as conn:
            return await conn.fetchval("SELECT 1") == 1

    async def save_many(self, positions: Sequence[VehiclePosition]) -> int:
        if not positions:
            return 0

        days = sorted({position.observed_at.astimezone(UTC).date() for position in positions})
        async with self.pool.acquire() as conn, conn.transaction():
            for day in days:
                partition_name = f"vehicle_positions_{day:%Y%m%d}"
                # Serialize old-day writes with destructive retention. Lock first, then
                # ensure the partition, so a late write after retention recreates safely.
                await conn.execute(
                    "SELECT pg_advisory_xact_lock(hashtext($1))", partition_name
                )
                await conn.execute("SELECT transit.ensure_vehicle_position_partition($1)", day)

            inserted = await conn.fetchval(
                """
                    WITH source_rows AS (
                        SELECT *
                        FROM unnest(
                            $1::text[], $2::text[], $3::text[], $4::text[], $5::text[],
                            $6::double precision[], $7::double precision[], $8::real[], $9::real[],
                            $10::timestamptz[], $11::timestamptz[], $12::text[], $13::text[],
                            $14::real[]
                        ) AS t(
                            ingest_key, agency_id, vehicle_id, route_id, trip_id,
                            latitude, longitude, speed_mps, bearing_deg, observed_at,
                            received_at, source, quality_status, quality_score
                        )
                    ), inserted_rows AS (
                        INSERT INTO transit.vehicle_positions (
                            ingest_key, agency_id, vehicle_id, route_id, trip_id,
                            latitude, longitude, speed_mps, bearing_deg,
                            observed_at, received_at, source, quality_status, quality_score,
                            location
                        )
                        SELECT
                            ingest_key, agency_id, vehicle_id, route_id, trip_id,
                            latitude, longitude, speed_mps, bearing_deg,
                            observed_at, received_at, source, quality_status, quality_score,
                            ST_SetSRID(ST_MakePoint(longitude, latitude),4326)::geography
                        FROM source_rows
                        ON CONFLICT (ingest_key, observed_at) DO NOTHING
                        RETURNING 1
                    )
                    SELECT count(*) FROM inserted_rows
                    """,
                [p.dedupe_key() for p in positions],
                [p.agency_id for p in positions],
                [p.vehicle_id for p in positions],
                [p.route_id for p in positions],
                [p.trip_id for p in positions],
                [p.latitude for p in positions],
                [p.longitude for p in positions],
                [p.speed_mps for p in positions],
                [p.bearing_deg for p in positions],
                [p.observed_at for p in positions],
                [p.received_at for p in positions],
                [p.source for p in positions],
                [p.quality_status.value for p in positions],
                [p.quality_score for p in positions],
            )

        return int(inserted or 0)

    async def nearby(
        self,
        *,
        latitude: float,
        longitude: float,
        radius_m: int,
        max_age_seconds: int,
        limit: int,
    ) -> Sequence[VehiclePosition]:
        cutoff = datetime.now(UTC) - timedelta(seconds=max_age_seconds)
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                WITH latest AS (
                    SELECT DISTINCT ON (agency_id, vehicle_id)
                        agency_id, vehicle_id, route_id, trip_id,
                        latitude, longitude, speed_mps, bearing_deg,
                        observed_at, received_at, source, quality_status, quality_score,
                        ST_Distance(
                            location,
                            ST_SetSRID(ST_MakePoint($2,$1),4326)::geography
                        ) AS distance_m
                    FROM transit.vehicle_positions
                    WHERE observed_at >= $4
                      AND quality_status <> 'invalid'
                      AND ST_DWithin(
                          location,
                          ST_SetSRID(ST_MakePoint($2,$1),4326)::geography,
                          $3
                      )
                    ORDER BY agency_id, vehicle_id, observed_at DESC
                )
                SELECT
                    agency_id, vehicle_id, route_id, trip_id,
                    latitude, longitude, speed_mps, bearing_deg,
                    observed_at, received_at, source, quality_status, quality_score
                FROM latest
                ORDER BY distance_m ASC
                LIMIT $5
                """,
                latitude,
                longitude,
                radius_m,
                cutoff,
                limit,
            )
        return [VehiclePosition.model_validate(dict(row)) for row in rows]


class PostgresQuarantineRepository:
    def __init__(self, pool: Any) -> None:
        self.pool = pool

    async def save_many(self, records: Sequence[RejectedSourceRecord]) -> int:
        if not records:
            return 0
        rows = [
            (
                r.source,
                r.payload_hash,
                r.reason_code,
                r.detail,
                json.dumps(r.raw_payload, ensure_ascii=False, default=str),
            )
            for r in records
        ]
        async with self.pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO transit.source_quarantine
                    (source, payload_hash, reason_code, detail, raw_payload)
                VALUES ($1,$2,$3,$4,$5::jsonb)
                ON CONFLICT (source, payload_hash, reason_code) DO UPDATE
                    SET last_seen_at = now(),
                        occurrence_count = transit.source_quarantine.occurrence_count + 1
                """,
                rows,
            )
        return len(records)


class PostgresIngestionRunRepository:
    def __init__(self, pool: Any) -> None:
        self.pool = pool

    async def record(self, report: Any) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO transit.ingestion_runs (
                    source, status, started_at, finished_at, received_records, rejected_records,
                    deduplicated_records, persisted_records, cached_records, quality_counts,
                    latest_observed_at, contract_fingerprint, observed_fields
                ) VALUES ($1,'success',$2,$3,$4,$5,$6,$7,$8,$9::jsonb,$10,$11,$12::jsonb)
                """,
                report.source,
                report.started_at,
                report.finished_at,
                report.received_records,
                report.rejected_records,
                report.deduplicated_records,
                report.persisted_records,
                report.cached_records,
                json.dumps(report.quality_counts),
                report.latest_observed_at,
                report.contract_fingerprint,
                json.dumps(report.observed_fields),
            )

    async def record_failure(
        self,
        *,
        source: str,
        started_at: datetime,
        error: Exception,
    ) -> None:
        detail = str(error)[:1000]
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO transit.ingestion_runs (
                    source, status, started_at, finished_at, received_records, rejected_records,
                    deduplicated_records, persisted_records, cached_records, quality_counts,
                    error_type, error_detail
                ) VALUES ($1,'failure',$2,now(),0,0,0,0,0,'{}'::jsonb,$3,$4)
                """,
                source,
                started_at,
                type(error).__name__,
                detail,
            )


class PostgresOperationalRepository:
    def __init__(self, pool: Any) -> None:
        self.pool = pool

    async def ingestion_runs_since(
        self,
        *,
        source: str,
        since: datetime,
    ) -> list[Any]:
        from app.modules.mobility.operations.models import IngestionRunSample

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    status, started_at, finished_at, received_records, rejected_records,
                    persisted_records, cached_records, contract_fingerprint
                FROM transit.ingestion_runs
                WHERE source = $1
                  AND finished_at >= $2
                ORDER BY finished_at
                """,
                source,
                since,
            )
        return [
            IngestionRunSample(
                status=row["status"],
                started_at=row["started_at"],
                finished_at=row["finished_at"],
                received_records=int(row["received_records"] or 0),
                rejected_records=int(row["rejected_records"] or 0),
                persisted_records=int(row["persisted_records"] or 0),
                cached_records=int(row["cached_records"] or 0),
                contract_fingerprint=row["contract_fingerprint"],
            )
            for row in rows
        ]

    async def latest_position_observed_at(self, *, source: str) -> datetime | None:
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                """
                SELECT latest_observed_at
                FROM transit.ingestion_runs
                WHERE source = $1
                  AND status = 'success'
                  AND latest_observed_at IS NOT NULL
                ORDER BY latest_observed_at DESC
                LIMIT 1
                """,
                source,
            )


class PostgresHotPartitionRepository:
    def __init__(self, pool: Any) -> None:
        self.pool = pool

    async def partition_days_before(self, *, cutoff: date) -> Sequence[date]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT to_date(right(child.relname, 8), 'YYYYMMDD') AS partition_day
                FROM pg_inherits
                JOIN pg_class parent ON pg_inherits.inhparent = parent.oid
                JOIN pg_class child ON pg_inherits.inhrelid = child.oid
                JOIN pg_namespace ns ON child.relnamespace = ns.oid
                WHERE ns.nspname = 'transit'
                  AND parent.relname = 'vehicle_positions'
                  AND child.relname ~ '^vehicle_positions_[0-9]{8}$'
                  AND to_date(right(child.relname, 8), 'YYYYMMDD') < $1
                ORDER BY partition_day
                """,
                cutoff,
            )
        return [row["partition_day"] for row in rows]

    @staticmethod
    def _partition_name(day: date) -> str:
        # Identifier is derived exclusively from a Python date, never from user/source text.
        return f"vehicle_positions_{day:%Y%m%d}"

    async def source_row_count(self, *, day: date, source: str) -> int:
        partition_name = self._partition_name(day)
        async with self.pool.acquire() as conn:
            value = await conn.fetchval(
                f'SELECT count(*) FROM transit."{partition_name}" WHERE source = $1',
                source,
            )
        return int(value or 0)

    async def contains_other_sources(self, *, day: date, source: str) -> bool:
        partition_name = self._partition_name(day)
        query = (
            f'SELECT EXISTS ('
            f'SELECT 1 FROM transit."{partition_name}" '
            'WHERE source <> $1 LIMIT 1)'
        )
        async with self.pool.acquire() as conn:
            value = await conn.fetchval(query, source)
        return bool(value)

    async def drop_partition_if_unchanged(
        self,
        *,
        day: date,
        source: str,
        expected_row_count: int,
    ) -> bool:
        partition_name = self._partition_name(day)
        async with self.pool.acquire() as conn, conn.transaction():
            await conn.execute("SELECT pg_advisory_xact_lock(hashtext($1))", partition_name)
            row = await conn.fetchrow(
                (
                    f'SELECT count(*) AS total_rows, '
                    f'count(*) FILTER (WHERE source = $1) AS source_rows '
                    f'FROM transit."{partition_name}"'
                ),
                source,
            )
            total_rows = int(row["total_rows"] or 0)
            source_rows = int(row["source_rows"] or 0)
            if total_rows != expected_row_count or source_rows != expected_row_count:
                return False
            await conn.execute(f'DROP TABLE transit."{partition_name}"')
            return True

class PostgresHistoricalPositionSource:
    def __init__(self, pool: Any) -> None:
        self.pool = pool

    async def iter_day(
        self,
        *,
        source: str,
        day: date,
        batch_size: int,
    ):
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        start = datetime.combine(day, datetime.min.time(), tzinfo=UTC)
        end = start + timedelta(days=1)
        async with self.pool.acquire() as conn, conn.transaction(readonly=True):
            cursor = conn.cursor(
                """
                    SELECT
                        agency_id, vehicle_id, route_id, trip_id,
                        latitude, longitude, speed_mps, bearing_deg,
                        observed_at, received_at, source, quality_status, quality_score
                    FROM transit.vehicle_positions
                    WHERE source = $1
                      AND observed_at >= $2
                      AND observed_at < $3
                    ORDER BY observed_at, ingest_key
                    """,
                source,
                start,
                end,
                prefetch=batch_size,
            )
            batch: list[VehiclePosition] = []
            async for row in cursor:
                batch.append(VehiclePosition.model_validate(dict(row)))
                if len(batch) >= batch_size:
                    yield batch
                    batch = []
            if batch:
                yield batch


class PostgresArchiveManifestCatalog:
    def __init__(self, pool: Any) -> None:
        self.pool = pool

    async def is_verified(self, *, source: str, day: date) -> bool:
        async with self.pool.acquire() as conn:
            value = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM transit.cold_archive_manifests
                    WHERE source = $1
                      AND archive_day = $2
                      AND status = 'verified'
                )
                """,
                source,
                day,
            )
        return bool(value)

    async def get_verified(self, *, source: str, day: date):
        from app.modules.mobility.archive.models import ArchiveArtifact

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT source, archive_day, object_uri, format, row_count, byte_size, sha256
                FROM transit.cold_archive_manifests
                WHERE source = $1 AND archive_day = $2 AND status = 'verified'
                """,
                source,
                day,
            )
        if row is None:
            return None
        return ArchiveArtifact.model_validate(dict(row))

    async def record_written(self, artifact: Any) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO transit.cold_archive_manifests (
                    source, archive_day, object_uri, format, row_count, byte_size, sha256,
                    status, written_at, verified_at, error_detail
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,'written',now(),NULL,NULL)
                ON CONFLICT (source, archive_day) DO UPDATE SET
                    object_uri = EXCLUDED.object_uri,
                    format = EXCLUDED.format,
                    row_count = EXCLUDED.row_count,
                    byte_size = EXCLUDED.byte_size,
                    sha256 = EXCLUDED.sha256,
                    status = 'written',
                    written_at = now(),
                    verified_at = NULL,
                    error_detail = NULL
                """,
                artifact.source,
                artifact.archive_day,
                artifact.object_uri,
                artifact.format,
                artifact.row_count,
                artifact.byte_size,
                artifact.sha256,
            )

    async def mark_verified(self, artifact: Any) -> None:
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE transit.cold_archive_manifests
                SET status = 'verified', verified_at = now(), error_detail = NULL
                WHERE source = $1
                  AND archive_day = $2
                  AND object_uri = $3
                  AND row_count = $4
                  AND byte_size = $5
                  AND sha256 = $6
                """,
                artifact.source,
                artifact.archive_day,
                artifact.object_uri,
                artifact.row_count,
                artifact.byte_size,
                artifact.sha256,
            )
            if result != "UPDATE 1":
                raise RuntimeError("archive manifest changed before verification commit")

    async def mark_failed(
        self,
        *,
        source: str,
        day: date,
        object_uri: str,
        detail: str,
    ) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE transit.cold_archive_manifests
                SET status = 'failed', verified_at = NULL, error_detail = $4
                WHERE source = $1 AND archive_day = $2 AND object_uri = $3
                """,
                source,
                day,
                object_uri,
                detail[:1000],
            )
