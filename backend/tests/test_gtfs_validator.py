from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from app.modules.mobility.gtfs.validator import (
    GtfsValidationError,
    validate_gtfs_snapshot,
)

MINIMUM_GTFS = {
    "stops.txt": "stop_id,stop_name,stop_lat,stop_lon\n1,Central,-22.9,-43.2\n",
    "routes.txt": "route_id,route_type\nA,3\n",
    "trips.txt": "route_id,service_id,trip_id\nA,WK,T1\n",
    "stop_times.txt": (
        "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
        "T1,08:00:00,08:00:00,1,1\n"
    ),
    "calendar_dates.txt": "service_id,date,exception_type\nWK,20260903,1\n",
}


def _write_zip(path: Path, files: dict[str, str]) -> None:
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        for filename, content in files.items():
            archive.writestr(filename, content)


def test_valid_minimum_gtfs_produces_a_content_addressed_manifest(tmp_path: Path) -> None:
    snapshot = tmp_path / "gtfs.zip"
    _write_zip(snapshot, MINIMUM_GTFS)
    fetched_at = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)

    manifest = validate_gtfs_snapshot(
        snapshot,
        source_url="https://www.arcgis.com/example/data",
        fetched_at=fetched_at,
    )

    assert len(manifest.snapshot_id) == 64
    assert manifest.fetched_at == fetched_at
    assert manifest.member_count == 5
    assert manifest.service_calendar_files == ("calendar_dates.txt",)
    assert {item.filename for item in manifest.files} == set(MINIMUM_GTFS)


def test_missing_core_file_is_rejected(tmp_path: Path) -> None:
    snapshot = tmp_path / "gtfs.zip"
    files = dict(MINIMUM_GTFS)
    del files["trips.txt"]
    _write_zip(snapshot, files)

    with pytest.raises(GtfsValidationError, match="missing: trips.txt"):
        validate_gtfs_snapshot(snapshot, source_url="https://www.arcgis.com/data")


def test_calendar_definition_is_required(tmp_path: Path) -> None:
    snapshot = tmp_path / "gtfs.zip"
    files = dict(MINIMUM_GTFS)
    del files["calendar_dates.txt"]
    _write_zip(snapshot, files)

    with pytest.raises(GtfsValidationError, match="requires calendar"):
        validate_gtfs_snapshot(snapshot, source_url="https://www.arcgis.com/data")


def test_path_traversal_is_rejected(tmp_path: Path) -> None:
    snapshot = tmp_path / "gtfs.zip"
    files = dict(MINIMUM_GTFS)
    files["../agency.txt"] = "agency_id,agency_name,agency_url,agency_timezone\n1,X,x,UTC\n"
    _write_zip(snapshot, files)

    with pytest.raises(GtfsValidationError, match="unsafe or unsupported"):
        validate_gtfs_snapshot(snapshot, source_url="https://www.arcgis.com/data")


def test_case_insensitive_duplicate_is_rejected(tmp_path: Path) -> None:
    snapshot = tmp_path / "gtfs.zip"
    files = dict(MINIMUM_GTFS)
    files["Stops.txt"] = files["stops.txt"]
    _write_zip(snapshot, files)

    with pytest.raises(GtfsValidationError, match="duplicate GTFS member"):
        validate_gtfs_snapshot(snapshot, source_url="https://www.arcgis.com/data")


def test_uncompressed_size_is_bounded(tmp_path: Path) -> None:
    snapshot = tmp_path / "gtfs.zip"
    _write_zip(snapshot, MINIMUM_GTFS)

    with pytest.raises(GtfsValidationError, match="uncompressed size limit"):
        validate_gtfs_snapshot(
            snapshot,
            source_url="https://www.arcgis.com/data",
            max_uncompressed_bytes=32,
        )


def test_missing_required_column_is_rejected(tmp_path: Path) -> None:
    snapshot = tmp_path / "gtfs.zip"
    files = dict(MINIMUM_GTFS)
    files["routes.txt"] = "route_id\nA\n"
    _write_zip(snapshot, files)

    with pytest.raises(GtfsValidationError, match="routes.txt is missing columns: route_type"):
        validate_gtfs_snapshot(snapshot, source_url="https://www.arcgis.com/data")


def test_expected_hash_is_enforced(tmp_path: Path) -> None:
    snapshot = tmp_path / "gtfs.zip"
    _write_zip(snapshot, MINIMUM_GTFS)

    with pytest.raises(GtfsValidationError, match="SHA-256 mismatch"):
        validate_gtfs_snapshot(
            snapshot,
            source_url="https://www.arcgis.com/data",
            expected_sha256="0" * 64,
        )
