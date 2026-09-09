from datetime import UTC, datetime

from app.modules.mobility.models import VehiclePosition


def test_dedupe_key_is_stable() -> None:
    position = VehiclePosition(
        agency_id="a",
        vehicle_id="v",
        route_id="457",
        latitude=-22.9,
        longitude=-43.2,
        observed_at=datetime(2026, 9, 1, 13, tzinfo=UTC),
        received_at=datetime(2026, 9, 1, 13, 0, 1, tzinfo=UTC),
        source="test",
    )
    clone = position.model_copy(update={"received_at": datetime(2026, 9, 1, 13, 0, 2, tzinfo=UTC)})
    assert position.dedupe_key() == clone.dedupe_key()
