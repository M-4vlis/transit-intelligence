from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from app.infrastructure.parquet import LocalParquetArchiveWriter, _safe_component
from app.modules.mobility.models import VehiclePosition


def test_archive_source_component_is_sanitized() -> None:
    assert _safe_component("rio-smtr-gps") == "rio-smtr-gps"
    assert _safe_component("../../danger") == "danger"
    with pytest.raises(ValueError):
        _safe_component("../..")


@pytest.mark.asyncio
async def test_local_parquet_writer_round_trip_when_pyarrow_is_available(tmp_path: Path) -> None:
    pytest.importorskip("pyarrow")
    writer = LocalParquetArchiveWriter(tmp_path)
    now = datetime(2026, 9, 1, 12, tzinfo=UTC)

    async def batches():
        yield [
            VehiclePosition(
                agency_id="a",
                vehicle_id="v1",
                route_id="457",
                latitude=-22.9,
                longitude=-43.2,
                speed_mps=5.0,
                observed_at=now,
                received_at=now,
                source="rio-smtr-gps",
            )
        ]

    artifact = await writer.write_day(
        source="rio-smtr-gps",
        day=date(2026, 9, 1),
        batches=batches(),
    )
    verification = await writer.verify(artifact)

    assert artifact.row_count == 1
    assert artifact.byte_size > 0
    assert artifact.local_path is not None and artifact.local_path.exists()
    assert verification.valid is True
