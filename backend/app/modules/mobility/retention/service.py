from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Protocol


class ArchiveVerificationCatalog(Protocol):
    async def is_verified(
        self,
        *,
        source: str,
        day: date,
        expected_row_count: int | None = None,
    ) -> bool: ...


class HotPartitionRepository(Protocol):
    async def partition_days_before(self, *, cutoff: date) -> Sequence[date]: ...

    async def source_row_count(self, *, day: date, source: str) -> int: ...

    async def contains_other_sources(self, *, day: date, source: str) -> bool: ...

    async def drop_partition_if_unchanged(
        self,
        *,
        day: date,
        source: str,
        expected_row_count: int,
    ) -> bool: ...


@dataclass(frozen=True, slots=True)
class RetentionReport:
    cutoff_day: date
    candidate_days: tuple[date, ...]
    dropped_days: tuple[date, ...]
    protected_days: tuple[date, ...]
    would_drop_days: tuple[date, ...] = ()


class SafeHotRetentionService:
    """Drop hot partitions only after source-complete cold verification.

    The policy fails closed. A partition is protected if its archive is missing/corrupt,
    its archived row count differs from hot data, or the day contains another source.
    """

    def __init__(
        self,
        *,
        source: str,
        hot_repository: HotPartitionRepository,
        archive_catalog: ArchiveVerificationCatalog,
        retention_days: int,
    ) -> None:
        if retention_days < 1:
            raise ValueError("retention_days must be >= 1")
        self.source = source
        self.hot_repository = hot_repository
        self.archive_catalog = archive_catalog
        self.retention_days = retention_days

    async def run_once(
        self,
        *,
        now: datetime | None = None,
        dry_run: bool = False,
    ) -> RetentionReport:
        now = now or datetime.now(UTC)
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)
        cutoff_day = now.astimezone(UTC).date() - timedelta(days=self.retention_days)
        candidates = tuple(
            sorted(await self.hot_repository.partition_days_before(cutoff=cutoff_day))
        )

        dropped: list[date] = []
        protected: list[date] = []
        would_drop: list[date] = []
        for day in candidates:
            # Partitions are time-based, while archives are source/day. A source-specific
            # archive must never authorize deletion of another source sharing the same day.
            if await self.hot_repository.contains_other_sources(day=day, source=self.source):
                protected.append(day)
                continue

            expected_row_count = await self.hot_repository.source_row_count(
                day=day, source=self.source
            )
            verified = await self.archive_catalog.is_verified(
                source=self.source,
                day=day,
                expected_row_count=expected_row_count,
            )
            if not verified:
                protected.append(day)
                continue
            if dry_run:
                would_drop.append(day)
                continue
            removed = await self.hot_repository.drop_partition_if_unchanged(
                day=day,
                source=self.source,
                expected_row_count=expected_row_count,
            )
            if not removed:
                protected.append(day)
                continue
            dropped.append(day)

        return RetentionReport(
            cutoff_day=cutoff_day,
            candidate_days=candidates,
            dropped_days=tuple(dropped),
            protected_days=tuple(protected),
            would_drop_days=tuple(would_drop),
        )
