from datetime import UTC, date, datetime

import pytest

from app.modules.mobility.retention.service import SafeHotRetentionService


class FakeHotRepository:
    def __init__(self, days, *, row_counts=None, mixed_days=None):
        self.days = days
        self.dropped = []
        self.row_counts = row_counts or {}
        self.mixed_days = set(mixed_days or [])

    async def partition_days_before(self, *, cutoff):
        return [day for day in self.days if day < cutoff]

    async def source_row_count(self, *, day, source):
        assert source == "rio-smtr-gps"
        return self.row_counts.get(day, 10)

    async def contains_other_sources(self, *, day, source):
        assert source == "rio-smtr-gps"
        return day in self.mixed_days

    async def drop_partition_if_unchanged(
        self, *, day, source, expected_row_count
    ):
        assert source == "rio-smtr-gps"
        if day in self.mixed_days:
            return False
        if self.row_counts.get(day, 10) != expected_row_count:
            return False
        self.dropped.append(day)
        return True


class FakeArchiveCatalog:
    def __init__(self, verified, *, row_counts=None):
        self.verified = set(verified)
        self.row_counts = row_counts or {}

    async def is_verified(self, *, source, day, expected_row_count=None):
        assert source == "rio-smtr-gps"
        if day not in self.verified:
            return False
        return self.row_counts.get(day, expected_row_count) == expected_row_count


@pytest.mark.asyncio
async def test_retention_drops_only_verified_archives() -> None:
    old_verified = date(2026, 8, 28)
    old_unverified = date(2026, 8, 29)
    recent = date(2026, 8, 31)
    hot = FakeHotRepository([old_verified, old_unverified, recent])
    archive = FakeArchiveCatalog([old_verified])
    service = SafeHotRetentionService(
        source="rio-smtr-gps",
        hot_repository=hot,
        archive_catalog=archive,
        retention_days=2,
    )

    report = await service.run_once(now=datetime(2026, 9, 1, 15, tzinfo=UTC))

    assert report.cutoff_day == date(2026, 8, 30)
    assert report.dropped_days == (old_verified,)
    assert report.protected_days == (old_unverified,)
    assert hot.dropped == [old_verified]


@pytest.mark.asyncio
async def test_retention_protects_mixed_source_partition() -> None:
    day = date(2026, 8, 28)
    hot = FakeHotRepository([day], mixed_days=[day])
    archive = FakeArchiveCatalog([day])
    service = SafeHotRetentionService(
        source="rio-smtr-gps",
        hot_repository=hot,
        archive_catalog=archive,
        retention_days=2,
    )

    report = await service.run_once(now=datetime(2026, 9, 1, 15, tzinfo=UTC))

    assert report.dropped_days == ()
    assert report.protected_days == (day,)
    assert hot.dropped == []


@pytest.mark.asyncio
async def test_retention_protects_partition_when_archive_row_count_is_stale() -> None:
    day = date(2026, 8, 28)
    hot = FakeHotRepository([day], row_counts={day: 11})
    archive = FakeArchiveCatalog([day], row_counts={day: 10})
    service = SafeHotRetentionService(
        source="rio-smtr-gps",
        hot_repository=hot,
        archive_catalog=archive,
        retention_days=2,
    )

    report = await service.run_once(now=datetime(2026, 9, 1, 15, tzinfo=UTC))

    assert report.dropped_days == ()
    assert report.protected_days == (day,)
    assert hot.dropped == []


def test_retention_rejects_zero_days() -> None:
    with pytest.raises(ValueError):
        SafeHotRetentionService(
            source="rio-smtr-gps",
            hot_repository=FakeHotRepository([]),
            archive_catalog=FakeArchiveCatalog([]),
            retention_days=0,
        )


@pytest.mark.asyncio
async def test_retention_protects_partition_if_hot_rows_change_during_final_drop() -> None:
    day = date(2026, 8, 28)

    class RacingHotRepository(FakeHotRepository):
        async def drop_partition_if_unchanged(
            self, *, day, source, expected_row_count
        ):
            self.row_counts[day] = expected_row_count + 1
            return False

    hot = RacingHotRepository([day], row_counts={day: 10})
    archive = FakeArchiveCatalog([day], row_counts={day: 10})
    service = SafeHotRetentionService(
        source="rio-smtr-gps",
        hot_repository=hot,
        archive_catalog=archive,
        retention_days=2,
    )

    report = await service.run_once(now=datetime(2026, 9, 1, 15, tzinfo=UTC))

    assert report.dropped_days == ()
    assert report.protected_days == (day,)


@pytest.mark.asyncio
async def test_retention_dry_run_reports_eligible_days_without_dropping() -> None:
    verified = date(2026, 8, 28)
    unverified = date(2026, 8, 29)
    hot = FakeHotRepository([verified, unverified])
    archive = FakeArchiveCatalog([verified])
    service = SafeHotRetentionService(
        source="rio-smtr-gps",
        hot_repository=hot,
        archive_catalog=archive,
        retention_days=2,
    )

    report = await service.run_once(
        now=datetime(2026, 9, 1, 15, tzinfo=UTC),
        dry_run=True,
    )

    assert report.dropped_days == ()
    assert report.would_drop_days == (verified,)
    assert report.protected_days == (unverified,)
    assert hot.dropped == []
