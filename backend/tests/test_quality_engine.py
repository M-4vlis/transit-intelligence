from datetime import UTC, datetime, timedelta

from app.modules.mobility.models import QualityStatus, VehiclePosition
from app.modules.mobility.quality.engine import VehicleQualityEngine

NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


def position(*, age_seconds: int = 10, speed_mps: float | None = 10) -> VehiclePosition:
    return VehiclePosition(
        agency_id="rio",
        vehicle_id="D1",
        route_id="457",
        latitude=-22.9,
        longitude=-43.2,
        speed_mps=speed_mps,
        observed_at=NOW - timedelta(seconds=age_seconds),
        received_at=NOW,
        source="test",
    )


def test_fresh_position_is_good() -> None:
    result = VehicleQualityEngine().assess(position(), now=NOW)
    assert result.status == QualityStatus.GOOD
    assert result.score == 1
    assert result.reasons == ()


def test_stale_position_is_degraded() -> None:
    result = VehicleQualityEngine().assess(position(age_seconds=180), now=NOW)
    assert result.status == QualityStatus.DEGRADED
    assert "gps_stale" in result.reasons


def test_severely_stale_position_is_stale() -> None:
    result = VehicleQualityEngine().assess(position(age_seconds=600), now=NOW)
    assert result.status == QualityStatus.STALE
    assert "gps_severely_stale" in result.reasons


def test_implausible_speed_degrades_score() -> None:
    result = VehicleQualityEngine().assess(position(speed_mps=60), now=NOW)
    assert result.status == QualityStatus.DEGRADED
    assert "implausible_speed" in result.reasons
