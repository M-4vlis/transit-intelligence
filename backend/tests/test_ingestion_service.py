from datetime import UTC, datetime

import pytest

from app.modules.mobility.ingestion.service import IngestionService
from app.modules.mobility.models import RejectedSourceRecord, TransitBatch, VehiclePosition


class FakeAdapter:
    async def fetch_vehicle_positions(self) -> TransitBatch:
        p = VehiclePosition(
            agency_id="a",
            vehicle_id="v1",
            route_id="457",
            latitude=-22.9,
            longitude=-43.2,
            observed_at=datetime(2026, 9, 1, 13, 0, tzinfo=UTC),
            received_at=datetime(2026, 9, 1, 13, 0, 10, tzinfo=UTC),
            source="test",
        )
        rejected = RejectedSourceRecord.from_payload(
            source="test", payload={"bad": True}, reason_code="bad", detail="bad record"
        )
        return TransitBatch(
            source="test",
            fetched_at=datetime(2026, 9, 1, 13, 0, 10, tzinfo=UTC),
            positions=[p, p],
            rejected=[rejected],
        )


class FakeRepo:
    def __init__(self) -> None:
        self.saved = []

    async def save_many(self, positions):
        self.saved.extend(positions)
        return len(positions)


class FakeQuarantine:
    def __init__(self) -> None:
        self.saved = []

    async def save_many(self, records):
        self.saved.extend(records)
        return len(records)


class FakeCache:
    def __init__(self) -> None:
        self.saved = []

    async def put_many(self, positions):
        self.saved.extend(positions)
        return len(positions)


@pytest.mark.asyncio
async def test_ingestion_deduplicates_and_quarantines() -> None:
    repo = FakeRepo()
    quarantine = FakeQuarantine()
    cache = FakeCache()
    service = IngestionService(
        adapter=FakeAdapter(), repository=repo, quarantine=quarantine, cache=cache
    )

    report = await service.run_once()

    assert report.received_records == 3
    assert report.rejected_records == 1
    assert report.deduplicated_records == 1
    assert report.persisted_records == 1
    assert report.cached_records == 1
    assert report.latest_observed_at == datetime(2026, 9, 1, 13, 0, tzinfo=UTC)
    assert len(repo.saved) == 1
    assert len(quarantine.saved) == 1
