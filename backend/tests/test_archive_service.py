from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from app.modules.mobility.archive.models import ArchiveArtifact, ArchiveVerification
from app.modules.mobility.archive.service import ArchiveDayService, ArchiveVerificationError
from app.modules.mobility.models import VehiclePosition


DAY = date(2026, 9, 1)
SOURCE = "rio-smtr-gps"
SHA = "a" * 64


class FakeHistoricalSource:
    def __init__(self) -> None:
        self.calls = 0

    async def iter_day(self, *, source, day, batch_size):
        self.calls += 1
        assert source == SOURCE
        assert day == DAY
        assert batch_size == 2
        now = datetime(2026, 9, 1, 12, tzinfo=UTC)
        yield [
            VehiclePosition(
                agency_id="agency",
                vehicle_id="v1",
                route_id="457",
                latitude=-22.9,
                longitude=-43.2,
                observed_at=now,
                received_at=now,
                source=SOURCE,
            )
        ]


class FakeWriter:
    def __init__(self, *, valid=True) -> None:
        self.valid = valid
        self.write_calls = 0

    async def write_day(self, *, source, day, batches):
        self.write_calls += 1
        rows = 0
        async for batch in batches:
            rows += len(batch)
        return ArchiveArtifact(
            source=source,
            archive_day=day,
            object_uri="file:///archive/day.parquet",
            local_path=Path("/archive/day.parquet"),
            row_count=rows,
            byte_size=123,
            sha256=SHA,
        )

    async def verify(self, artifact):
        return ArchiveVerification(
            valid=self.valid,
            row_count=artifact.row_count,
            byte_size=artifact.byte_size,
            sha256=artifact.sha256 if self.valid else "b" * 64,
            detail="corrupted" if not self.valid else "",
        )


class FakeCatalog:
    def __init__(self, *, verified=False) -> None:
        self.verified = verified
        self.written = []
        self.verified_artifacts = []
        self.failed = []

    async def is_verified(self, *, source, day):
        assert source == SOURCE
        assert day == DAY
        return self.verified

    async def record_written(self, artifact):
        self.written.append(artifact)

    async def mark_verified(self, artifact):
        self.verified_artifacts.append(artifact)

    async def mark_failed(self, **kwargs):
        self.failed.append(kwargs)


@pytest.mark.asyncio
async def test_archive_day_writes_verifies_and_commits_manifest() -> None:
    source = FakeHistoricalSource()
    writer = FakeWriter()
    catalog = FakeCatalog()
    service = ArchiveDayService(
        source=SOURCE,
        historical_source=source,
        writer=writer,
        catalog=catalog,
        batch_size=2,
    )

    report = await service.run_day(day=DAY)

    assert report.status == "verified"
    assert report.row_count == 1
    assert report.sha256 == SHA
    assert len(catalog.written) == 1
    assert len(catalog.verified_artifacts) == 1
    assert catalog.failed == []


@pytest.mark.asyncio
async def test_archive_day_is_idempotent_when_manifest_is_already_verified() -> None:
    source = FakeHistoricalSource()
    writer = FakeWriter()
    catalog = FakeCatalog(verified=True)
    service = ArchiveDayService(
        source=SOURCE,
        historical_source=source,
        writer=writer,
        catalog=catalog,
        batch_size=2,
    )

    report = await service.run_day(day=DAY)

    assert report.skipped_existing is True
    assert writer.write_calls == 0
    assert source.calls == 0


@pytest.mark.asyncio
async def test_archive_verification_failure_is_recorded_and_blocks_success() -> None:
    catalog = FakeCatalog()
    service = ArchiveDayService(
        source=SOURCE,
        historical_source=FakeHistoricalSource(),
        writer=FakeWriter(valid=False),
        catalog=catalog,
        batch_size=2,
    )

    with pytest.raises(ArchiveVerificationError):
        await service.run_day(day=DAY)

    assert len(catalog.failed) == 1
    assert catalog.verified_artifacts == []


def test_archive_day_rejects_invalid_batch_size() -> None:
    with pytest.raises(ValueError):
        ArchiveDayService(
            source=SOURCE,
            historical_source=FakeHistoricalSource(),
            writer=FakeWriter(),
            catalog=FakeCatalog(),
            batch_size=0,
        )
