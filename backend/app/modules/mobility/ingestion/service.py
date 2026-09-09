from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime

from app.modules.mobility.adapters.base import TransitRealtimeAdapter
from app.modules.mobility.models import QualityStatus
from app.modules.mobility.ports import LivePositionCache, PositionRepository, QuarantineRepository
from app.modules.mobility.quality.engine import VehicleQualityEngine


@dataclass(frozen=True, slots=True)
class IngestionReport:
    source: str
    started_at: datetime
    finished_at: datetime
    received_records: int
    rejected_records: int
    deduplicated_records: int
    persisted_records: int
    cached_records: int
    quality_counts: dict[str, int]
    latest_observed_at: datetime | None = None
    contract_fingerprint: str | None = None
    observed_fields: tuple[str, ...] = ()


class IngestionService:
    def __init__(
        self,
        *,
        adapter: TransitRealtimeAdapter,
        repository: PositionRepository,
        quarantine: QuarantineRepository,
        cache: LivePositionCache,
        quality_engine: VehicleQualityEngine | None = None,
    ) -> None:
        self.adapter = adapter
        self.repository = repository
        self.quarantine = quarantine
        self.cache = cache
        self.quality_engine = quality_engine or VehicleQualityEngine()

    async def run_once(self) -> IngestionReport:
        started_at = datetime.now(UTC)
        batch = await self.adapter.fetch_vehicle_positions()

        if batch.rejected:
            await self.quarantine.save_many(batch.rejected)

        deduped = {}
        for position in batch.positions:
            assessed = self.quality_engine.apply(position, now=batch.fetched_at)
            deduped[assessed.dedupe_key()] = assessed

        positions = list(deduped.values())
        persisted = await self.repository.save_many(positions) if positions else 0

        cacheable = [
            position
            for position in positions
            if position.quality_status is not QualityStatus.INVALID
        ]
        cached = await self.cache.put_many(cacheable) if cacheable else 0
        quality_counts = Counter(position.quality_status.value for position in positions)

        return IngestionReport(
            source=batch.source,
            started_at=started_at,
            finished_at=datetime.now(UTC),
            received_records=len(batch.positions) + len(batch.rejected),
            rejected_records=len(batch.rejected),
            deduplicated_records=len(batch.positions) - len(positions),
            persisted_records=persisted,
            cached_records=cached,
            quality_counts=dict(quality_counts),
            latest_observed_at=max(
                (position.observed_at.astimezone(UTC) for position in positions),
                default=None,
            ),
            contract_fingerprint=batch.contract_fingerprint,
            observed_fields=tuple(batch.observed_fields),
        )
