from __future__ import annotations

import csv
import io
import json
from collections.abc import Callable, Iterator, Sequence
from datetime import date
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from app.modules.mobility.gtfs.models import (
    GtfsImportResult,
    GtfsSnapshotManifest,
    GtfsStopDistanceRehydrationResult,
)

_BATCH_SIZE = 20_000


class GtfsImportError(ValueError):
    pass


def _text(value: str | None, *, required: bool = False) -> str | None:
    normalized = (value or "").strip()
    if required and not normalized:
        raise GtfsImportError("required GTFS value is blank")
    return normalized or None


def _integer(value: str | None, *, required: bool = False) -> int | None:
    normalized = _text(value, required=required)
    if normalized is None:
        return None
    try:
        return int(normalized)
    except ValueError as exc:
        raise GtfsImportError(f"invalid GTFS integer: {normalized!r}") from exc


def _number(value: str | None, *, required: bool = False) -> float | None:
    normalized = _text(value, required=required)
    if normalized is None:
        return None
    try:
        return float(normalized)
    except ValueError as exc:
        raise GtfsImportError(f"invalid GTFS number: {normalized!r}") from exc


def _boolean(value: str | None) -> bool:
    parsed = _integer(value, required=True)
    if parsed not in {0, 1}:
        raise GtfsImportError(f"invalid GTFS boolean: {value!r}")
    return bool(parsed)


def _service_date(value: str | None) -> date:
    normalized = _text(value, required=True)
    try:
        return date(int(normalized[0:4]), int(normalized[4:6]), int(normalized[6:8]))
    except (TypeError, ValueError, IndexError) as exc:
        raise GtfsImportError(f"invalid GTFS date: {normalized!r}") from exc


def gtfs_time_to_seconds(value: str | None) -> int | None:
    normalized = _text(value)
    if normalized is None:
        return None
    parts = normalized.split(":")
    if len(parts) != 3:
        raise GtfsImportError(f"invalid GTFS time: {normalized!r}")
    try:
        hours, minutes, seconds = (int(part) for part in parts)
    except ValueError as exc:
        raise GtfsImportError(f"invalid GTFS time: {normalized!r}") from exc
    if hours < 0 or minutes not in range(60) or seconds not in range(60):
        raise GtfsImportError(f"invalid GTFS time: {normalized!r}")
    return hours * 3600 + minutes * 60 + seconds


def _agency(row: dict[str, str], snapshot_id: str) -> tuple[Any, ...]:
    return (
        snapshot_id,
        _text(row.get("agency_id")) or "__default__",
        _text(row.get("agency_name"), required=True),
        _text(row.get("agency_url")),
        _text(row.get("agency_timezone")),
        _text(row.get("agency_lang")),
        _text(row.get("agency_phone")),
    )


def _route(row: dict[str, str], snapshot_id: str) -> tuple[Any, ...]:
    return (
        snapshot_id,
        _text(row.get("route_id"), required=True),
        _text(row.get("agency_id")),
        _text(row.get("route_short_name")),
        _text(row.get("route_long_name")),
        _text(row.get("route_desc")),
        _integer(row.get("route_type"), required=True),
        _text(row.get("route_color")),
        _text(row.get("route_text_color")),
    )


def _stop(row: dict[str, str], snapshot_id: str) -> tuple[Any, ...]:
    return (
        snapshot_id,
        _text(row.get("stop_id"), required=True),
        _text(row.get("stop_code")),
        _text(row.get("stop_name"), required=True),
        _text(row.get("stop_desc")),
        _number(row.get("stop_lat"), required=True),
        _number(row.get("stop_lon"), required=True),
        _text(row.get("zone_id")),
        _integer(row.get("location_type")),
        _text(row.get("parent_station")),
        _integer(row.get("wheelchair_boarding")),
    )


def _trip(row: dict[str, str], snapshot_id: str) -> tuple[Any, ...]:
    return (
        snapshot_id,
        _text(row.get("trip_id"), required=True),
        _text(row.get("route_id"), required=True),
        _text(row.get("service_id"), required=True),
        _text(row.get("trip_headsign")),
        _integer(row.get("direction_id")),
        _text(row.get("block_id")),
        _text(row.get("shape_id")),
        _integer(row.get("wheelchair_accessible")),
    )


def _stop_time(row: dict[str, str], snapshot_id: str) -> tuple[Any, ...]:
    return (
        snapshot_id,
        _text(row.get("trip_id"), required=True),
        _integer(row.get("stop_sequence"), required=True),
        gtfs_time_to_seconds(row.get("arrival_time")),
        gtfs_time_to_seconds(row.get("departure_time")),
        _text(row.get("stop_id"), required=True),
        _text(row.get("stop_headsign")),
        _integer(row.get("pickup_type")),
        _integer(row.get("drop_off_type")),
        _integer(row.get("timepoint")),
        _number(row.get("shape_dist_traveled")),
    )


def _stop_distance(row: dict[str, str], snapshot_id: str) -> tuple[Any, ...]:
    return (
        snapshot_id,
        _text(row.get("trip_id"), required=True),
        _integer(row.get("stop_sequence"), required=True),
        _number(row.get("shape_dist_traveled")),
    )


def _calendar(row: dict[str, str], snapshot_id: str) -> tuple[Any, ...]:
    return (
        snapshot_id,
        _text(row.get("service_id"), required=True),
        _boolean(row.get("monday")),
        _boolean(row.get("tuesday")),
        _boolean(row.get("wednesday")),
        _boolean(row.get("thursday")),
        _boolean(row.get("friday")),
        _boolean(row.get("saturday")),
        _boolean(row.get("sunday")),
        _service_date(row.get("start_date")),
        _service_date(row.get("end_date")),
    )


def _calendar_date(row: dict[str, str], snapshot_id: str) -> tuple[Any, ...]:
    return (
        snapshot_id,
        _text(row.get("service_id"), required=True),
        _service_date(row.get("date")),
        _integer(row.get("exception_type"), required=True),
    )


def _shape(row: dict[str, str], snapshot_id: str) -> tuple[Any, ...]:
    return (
        snapshot_id,
        _text(row.get("shape_id"), required=True),
        _integer(row.get("shape_pt_sequence"), required=True),
        _number(row.get("shape_pt_lat"), required=True),
        _number(row.get("shape_pt_lon"), required=True),
        _number(row.get("shape_dist_traveled")),
    )


_FileSpec = tuple[str, str, tuple[str, ...], Callable[[dict[str, str], str], tuple[Any, ...]]]
_FILE_SPECS: tuple[_FileSpec, ...] = (
    (
        "agency.txt",
        "gtfs_agencies",
        (
            "snapshot_id",
            "agency_id",
            "agency_name",
            "agency_url",
            "agency_timezone",
            "agency_lang",
            "agency_phone",
        ),
        _agency,
    ),
    (
        "routes.txt",
        "gtfs_routes",
        (
            "snapshot_id",
            "route_id",
            "agency_id",
            "route_short_name",
            "route_long_name",
            "route_desc",
            "route_type",
            "route_color",
            "route_text_color",
        ),
        _route,
    ),
    (
        "stops.txt",
        "gtfs_stops",
        (
            "snapshot_id",
            "stop_id",
            "stop_code",
            "stop_name",
            "stop_desc",
            "stop_lat",
            "stop_lon",
            "zone_id",
            "location_type",
            "parent_station",
            "wheelchair_boarding",
        ),
        _stop,
    ),
    (
        "trips.txt",
        "gtfs_trips",
        (
            "snapshot_id",
            "trip_id",
            "route_id",
            "service_id",
            "trip_headsign",
            "direction_id",
            "block_id",
            "shape_id",
            "wheelchair_accessible",
        ),
        _trip,
    ),
    (
        "stop_times.txt",
        "gtfs_stop_times",
        (
            "snapshot_id",
            "trip_id",
            "stop_sequence",
            "arrival_seconds",
            "departure_seconds",
            "stop_id",
            "stop_headsign",
            "pickup_type",
            "drop_off_type",
            "timepoint",
            "shape_dist_traveled",
        ),
        _stop_time,
    ),
    (
        "calendar.txt",
        "gtfs_calendars",
        (
            "snapshot_id",
            "service_id",
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
            "start_date",
            "end_date",
        ),
        _calendar,
    ),
    (
        "calendar_dates.txt",
        "gtfs_calendar_dates",
        ("snapshot_id", "service_id", "service_date", "exception_type"),
        _calendar_date,
    ),
    (
        "shapes.txt",
        "gtfs_shapes",
        (
            "snapshot_id",
            "shape_id",
            "shape_pt_sequence",
            "shape_pt_lat",
            "shape_pt_lon",
            "shape_dist_traveled",
        ),
        _shape,
    ),
)


def _rows(
    archive: ZipFile,
    member_name: str,
    snapshot_id: str,
    parser: Callable[[dict[str, str], str], tuple[Any, ...]],
) -> Iterator[tuple[Any, ...]]:
    with (
        archive.open(member_name, "r") as raw,
        io.TextIOWrapper(raw, encoding="utf-8-sig", newline="") as text,
    ):
        reader = csv.DictReader(text)
        for line_number, row in enumerate(reader, start=2):
            try:
                yield parser(row, snapshot_id)
            except GtfsImportError as exc:
                raise GtfsImportError(f"{member_name}:{line_number}: {exc}") from exc


async def _copy_rows(
    conn: Any,
    *,
    table_name: str,
    columns: Sequence[str],
    rows: Iterator[tuple[Any, ...]],
    schema_name: str | None = "transit",
) -> int:
    count = 0
    batch: list[tuple[Any, ...]] = []
    for row in rows:
        batch.append(row)
        if len(batch) >= _BATCH_SIZE:
            await conn.copy_records_to_table(
                table_name,
                schema_name=schema_name,
                records=batch,
                columns=columns,
            )
            count += len(batch)
            batch = []
    if batch:
        await conn.copy_records_to_table(
            table_name,
            schema_name=schema_name,
            records=batch,
            columns=columns,
        )
        count += len(batch)
    return count


async def _activate(conn: Any, snapshot_id: str) -> None:
    exists = await conn.fetchval(
        "SELECT 1 FROM transit.gtfs_snapshots WHERE snapshot_id = $1", snapshot_id
    )
    if not exists:
        raise GtfsImportError("GTFS snapshot is not imported")
    await conn.execute(
        "UPDATE transit.gtfs_snapshots SET status = 'superseded' "
        "WHERE status = 'active' AND snapshot_id <> $1",
        snapshot_id,
    )
    await conn.execute(
        "UPDATE transit.gtfs_snapshots SET status = 'active' WHERE snapshot_id = $1",
        snapshot_id,
    )


class PostgresGtfsImporter:
    def __init__(self, pool: Any) -> None:
        self.pool = pool

    async def import_snapshot(
        self,
        path: Path,
        manifest: GtfsSnapshotManifest,
        *,
        activate: bool = True,
    ) -> GtfsImportResult:
        manifest_json = json.dumps(manifest.model_dump(mode="json"), sort_keys=True)
        async with self.pool.acquire() as conn, conn.transaction():
            await conn.execute("SELECT pg_advisory_xact_lock(hashtext('gtfs-snapshot-import'))")
            existing = await conn.fetchrow(
                "SELECT status,row_counts FROM transit.gtfs_snapshots WHERE snapshot_id = $1",
                manifest.snapshot_id,
            )
            if existing is not None:
                if activate:
                    await _activate(conn, manifest.snapshot_id)
                raw_counts = existing["row_counts"]
                decoded_counts = (
                    json.loads(raw_counts) if isinstance(raw_counts, str) else raw_counts
                )
                return GtfsImportResult(
                    snapshot_id=manifest.snapshot_id,
                    active=activate or existing["status"] == "active",
                    already_imported=True,
                    row_counts={
                        str(key): int(value) for key, value in dict(decoded_counts).items()
                    },
                )

            await conn.execute(
                """
                INSERT INTO transit.gtfs_snapshots (
                    snapshot_id, source_id, source_url, fetched_at, status, manifest
                ) VALUES ($1,$2,$3,$4,'importing',$5::jsonb)
                """,
                manifest.snapshot_id,
                manifest.source_id,
                manifest.source_url,
                manifest.fetched_at,
                manifest_json,
            )

            counts: dict[str, int] = {}
            with ZipFile(path, "r") as archive:
                names = {name.casefold(): name for name in archive.namelist()}
                for filename, table_name, columns, parser in _FILE_SPECS:
                    member_name = names.get(filename)
                    if member_name is None:
                        counts[filename] = 0
                        continue
                    counts[filename] = await _copy_rows(
                        conn,
                        table_name=table_name,
                        columns=columns,
                        rows=_rows(archive, member_name, manifest.snapshot_id, parser),
                    )

            await conn.execute(
                "UPDATE transit.gtfs_snapshots SET status = 'ready', row_counts = $2::jsonb "
                "WHERE snapshot_id = $1",
                manifest.snapshot_id,
                json.dumps(counts, sort_keys=True),
            )
            if activate:
                await _activate(conn, manifest.snapshot_id)

        return GtfsImportResult(
            snapshot_id=manifest.snapshot_id,
            active=activate,
            row_counts=counts,
        )

    async def activate_snapshot(self, snapshot_id: str) -> None:
        async with self.pool.acquire() as conn, conn.transaction():
            await conn.execute("SELECT pg_advisory_xact_lock(hashtext('gtfs-snapshot-import'))")
            await _activate(conn, snapshot_id)

    async def rehydrate_stop_distances(
        self,
        path: Path,
        manifest: GtfsSnapshotManifest,
    ) -> GtfsStopDistanceRehydrationResult:
        """Fill stop distances only when the validated source is the active snapshot."""
        async with self.pool.acquire() as conn, conn.transaction():
            await conn.execute("SELECT pg_advisory_xact_lock(hashtext('gtfs-snapshot-import'))")
            snapshot = await conn.fetchrow(
                "SELECT status FROM transit.gtfs_snapshots WHERE snapshot_id = $1",
                manifest.snapshot_id,
            )
            if snapshot is None:
                raise GtfsImportError("validated GTFS snapshot is not imported")
            if snapshot["status"] != "active":
                raise GtfsImportError("validated GTFS snapshot is not active")

            await conn.execute(
                """
                CREATE TEMP TABLE gtfs_stop_distance_stage (
                    snapshot_id text NOT NULL,
                    trip_id text NOT NULL,
                    stop_sequence integer NOT NULL,
                    shape_dist_traveled double precision,
                    PRIMARY KEY (snapshot_id, trip_id, stop_sequence)
                ) ON COMMIT DROP
                """
            )
            with ZipFile(path, "r") as archive:
                names = {name.casefold(): name for name in archive.namelist()}
                member_name = names.get("stop_times.txt")
                if member_name is None:
                    raise GtfsImportError("GTFS archive is missing stop_times.txt")
                staged_rows = await _copy_rows(
                    conn,
                    table_name="gtfs_stop_distance_stage",
                    columns=(
                        "snapshot_id",
                        "trip_id",
                        "stop_sequence",
                        "shape_dist_traveled",
                    ),
                    rows=_rows(archive, member_name, manifest.snapshot_id, _stop_distance),
                    schema_name=None,
                )

            counts = await conn.fetchrow(
                """
                SELECT
                    count(*)::bigint AS staged_rows,
                    count(shape_dist_traveled)::bigint AS source_non_null_rows,
                    count(t.snapshot_id)::bigint AS matched_rows,
                    (
                        SELECT count(*)
                        FROM transit.gtfs_stop_times
                        WHERE snapshot_id = $1
                    )::bigint AS target_rows
                FROM gtfs_stop_distance_stage s
                LEFT JOIN transit.gtfs_stop_times t
                  ON t.snapshot_id = s.snapshot_id
                 AND t.trip_id = s.trip_id
                 AND t.stop_sequence = s.stop_sequence
                """,
                manifest.snapshot_id,
            )
            if counts is None or int(counts["staged_rows"]) != staged_rows:
                raise GtfsImportError("GTFS stop-distance staging count mismatch")
            source_non_null_rows = int(counts["source_non_null_rows"])
            if source_non_null_rows == 0:
                raise GtfsImportError("GTFS snapshot has no stop shape distances")
            if (
                int(counts["matched_rows"]) != staged_rows
                or int(counts["target_rows"]) != staged_rows
            ):
                raise GtfsImportError("GTFS source rows do not exactly match the active snapshot")
            invalid_distance_rows = int(
                await conn.fetchval(
                    """
                    SELECT count(*)
                    FROM (
                        SELECT
                            shape_dist_traveled,
                            lag(shape_dist_traveled) OVER (
                                PARTITION BY trip_id ORDER BY stop_sequence
                            ) AS previous_distance
                        FROM gtfs_stop_distance_stage
                    ) distances
                    WHERE shape_dist_traveled < 0
                       OR shape_dist_traveled < previous_distance
                    """
                )
            )
            if invalid_distance_rows:
                raise GtfsImportError("GTFS stop shape distances are negative or decreasing")

            update_status = await conn.execute(
                """
                UPDATE transit.gtfs_stop_times target
                   SET shape_dist_traveled = source.shape_dist_traveled
                  FROM gtfs_stop_distance_stage source
                 WHERE target.snapshot_id = source.snapshot_id
                   AND target.trip_id = source.trip_id
                   AND target.stop_sequence = source.stop_sequence
                   AND source.shape_dist_traveled IS NOT NULL
                   AND target.shape_dist_traveled IS DISTINCT FROM source.shape_dist_traveled
                """
            )
            updated_rows = int(update_status.rsplit(" ", 1)[-1])
            target_non_null_rows = int(
                await conn.fetchval(
                    """
                    SELECT count(*)
                    FROM transit.gtfs_stop_times
                    WHERE snapshot_id = $1 AND shape_dist_traveled IS NOT NULL
                    """,
                    manifest.snapshot_id,
                )
            )
            if target_non_null_rows != source_non_null_rows:
                raise GtfsImportError("rehydrated stop-distance count failed verification")

        return GtfsStopDistanceRehydrationResult(
            snapshot_id=manifest.snapshot_id,
            staged_rows=staged_rows,
            source_non_null_rows=source_non_null_rows,
            source_null_rows=staged_rows - source_non_null_rows,
            updated_rows=updated_rows,
            target_non_null_rows=target_non_null_rows,
        )
