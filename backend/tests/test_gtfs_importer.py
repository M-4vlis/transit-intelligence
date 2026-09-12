from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from app.modules.mobility.gtfs.importer import (
    GtfsImportError,
    PostgresGtfsImporter,
    gtfs_time_to_seconds,
)
from app.modules.mobility.gtfs.validator import validate_gtfs_snapshot

GTFS = {
    "agency.txt": (
        "agency_id,agency_name,agency_url,agency_timezone\n"
        "RIO,SMTR,https://transportes.prefeitura.rio,America/Sao_Paulo\n"
    ),
    "routes.txt": (
        "route_id,agency_id,route_short_name,route_long_name,route_type\n"
        "483,RIO,483,Penha - General Osorio,3\n"
    ),
    "stops.txt": "stop_id,stop_name,stop_lat,stop_lon\nS1,Central,-22.9,-43.2\n",
    "trips.txt": ("route_id,service_id,trip_id,shape_id\n483,WK,T1,SH1\n"),
    "stop_times.txt": (
        "trip_id,arrival_time,departure_time,stop_id,stop_sequence,shape_dist_traveled\n"
        "T1,25:01:02,25:01:02,S1,1,123.4\n"
    ),
    "calendar_dates.txt": "service_id,date,exception_type\nWK,20260911,1\n",
    "shapes.txt": ("shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence\nSH1,-22.9,-43.2,1\n"),
}


class _Context(AbstractAsyncContextManager[Any]):
    def __init__(self, value: Any) -> None:
        self.value = value

    async def __aenter__(self) -> Any:
        return self.value

    async def __aexit__(self, *args: object) -> None:
        return None


class FakeConnection:
    def __init__(self, *, existing: dict[str, Any] | None = None) -> None:
        self.copied: dict[str, list[tuple[Any, ...]]] = {}
        self.queries: list[str] = []
        self.existing = existing

    def transaction(self) -> _Context:
        return _Context(None)

    async def execute(self, query: str, *args: Any) -> str:
        self.queries.append(" ".join(query.split()))
        return "OK"

    async def fetchrow(self, query: str, *args: Any) -> dict[str, Any] | None:
        return self.existing

    async def fetchval(self, query: str, *args: Any) -> int:
        return 1

    async def copy_records_to_table(
        self,
        table_name: str,
        *,
        records: list[tuple[Any, ...]],
        **kwargs: Any,
    ) -> None:
        self.copied.setdefault("__schemas__", []).append((table_name, kwargs.get("schema_name")))
        self.copied.setdefault(table_name, []).extend(records)


class FakePool:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    def acquire(self) -> _Context:
        return _Context(self.connection)


class RehydrateFakeConnection(FakeConnection):
    def __init__(self, *, status: str = "active", matched_rows: int = 1) -> None:
        super().__init__()
        self.status = status
        self.matched_rows = matched_rows

    async def execute(self, query: str, *args: Any) -> str:
        await super().execute(query, *args)
        if "UPDATE transit.gtfs_stop_times target" in query:
            return "UPDATE 1"
        return "OK"

    async def fetchrow(self, query: str, *args: Any) -> dict[str, Any] | None:
        self.queries.append(" ".join(query.split()))
        if "SELECT status FROM transit.gtfs_snapshots" in query:
            return {"status": self.status}
        if "FROM gtfs_stop_distance_stage" in query:
            return {
                "staged_rows": 1,
                "source_non_null_rows": 1,
                "matched_rows": self.matched_rows,
                "target_rows": 1,
            }
        return None

    async def fetchval(self, query: str, *args: Any) -> int:
        if "lag(shape_dist_traveled)" in query:
            return 0
        return 1


def _write_gtfs(path: Path) -> None:
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        for filename, content in GTFS.items():
            archive.writestr(filename, content)


def test_gtfs_time_supports_service_after_midnight() -> None:
    assert gtfs_time_to_seconds("25:01:02") == 90_062
    assert gtfs_time_to_seconds("") is None
    with pytest.raises(GtfsImportError, match="invalid GTFS time"):
        gtfs_time_to_seconds("12:99:00")


@pytest.mark.asyncio
async def test_snapshot_import_copies_all_supported_files_and_activates(tmp_path: Path) -> None:
    path = tmp_path / "gtfs.zip"
    _write_gtfs(path)
    manifest = validate_gtfs_snapshot(
        path,
        source_url="https://dados.mobilidade.rio/gtfs/schedule",
        fetched_at=datetime(2026, 9, 11, tzinfo=UTC),
    )
    connection = FakeConnection()

    result = await PostgresGtfsImporter(FakePool(connection)).import_snapshot(path, manifest)

    assert result.active is True
    assert result.already_imported is False
    assert result.row_counts["routes.txt"] == 1
    assert result.row_counts["shapes.txt"] == 1
    assert connection.copied["gtfs_stop_times"][0][3] == 90_062
    assert connection.copied["gtfs_stop_times"][0][-1] == 123.4
    assert any("status = 'active'" in query for query in connection.queries)


@pytest.mark.asyncio
async def test_reimport_is_idempotent_and_can_activate_ready_snapshot(tmp_path: Path) -> None:
    path = tmp_path / "gtfs.zip"
    _write_gtfs(path)
    manifest = validate_gtfs_snapshot(
        path,
        source_url="https://dados.mobilidade.rio/gtfs/schedule",
    )
    connection = FakeConnection(
        existing={"status": "ready", "row_counts": '{"routes.txt": 494}'}
    )

    result = await PostgresGtfsImporter(FakePool(connection)).import_snapshot(path, manifest)

    assert result.already_imported is True
    assert result.active is True
    assert result.row_counts == {"routes.txt": 494}
    assert connection.copied == {}
    assert any("status = 'superseded'" in query for query in connection.queries)
    assert any("status = 'active'" in query for query in connection.queries)


@pytest.mark.asyncio
async def test_stop_distances_are_rehydrated_only_for_exact_active_snapshot(
    tmp_path: Path,
) -> None:
    path = tmp_path / "gtfs.zip"
    _write_gtfs(path)
    manifest = validate_gtfs_snapshot(
        path,
        source_url="https://dados.mobilidade.rio/gtfs/schedule",
    )
    connection = RehydrateFakeConnection()

    result = await PostgresGtfsImporter(FakePool(connection)).rehydrate_stop_distances(
        path,
        manifest,
    )

    assert result.staged_rows == 1
    assert result.source_non_null_rows == 1
    assert result.source_null_rows == 0
    assert result.updated_rows == 1
    assert result.target_non_null_rows == 1
    assert connection.copied["gtfs_stop_distance_stage"][0] == (
        manifest.snapshot_id,
        "T1",
        1,
        123.4,
    )
    assert connection.copied["__schemas__"] == [("gtfs_stop_distance_stage", None)]
    assert any("count(s.shape_dist_traveled)" in query for query in connection.queries)


@pytest.mark.asyncio
async def test_stop_distance_rehydration_rejects_non_active_snapshot(tmp_path: Path) -> None:
    path = tmp_path / "gtfs.zip"
    _write_gtfs(path)
    manifest = validate_gtfs_snapshot(
        path,
        source_url="https://dados.mobilidade.rio/gtfs/schedule",
    )

    with pytest.raises(GtfsImportError, match="snapshot is not active"):
        await PostgresGtfsImporter(
            FakePool(RehydrateFakeConnection(status="ready"))
        ).rehydrate_stop_distances(path, manifest)


@pytest.mark.asyncio
async def test_stop_distance_rehydration_rejects_row_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "gtfs.zip"
    _write_gtfs(path)
    manifest = validate_gtfs_snapshot(
        path,
        source_url="https://dados.mobilidade.rio/gtfs/schedule",
    )

    with pytest.raises(GtfsImportError, match="do not exactly match"):
        await PostgresGtfsImporter(
            FakePool(RehydrateFakeConnection(matched_rows=0))
        ).rehydrate_stop_distances(path, manifest)
