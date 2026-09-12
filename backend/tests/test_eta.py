from datetime import UTC, datetime, timedelta

from app.modules.mobility.eta import estimate_stop_arrivals
from app.modules.mobility.gtfs.models import (
    EtaEvidence,
    EtaMethod,
    EtaUnavailableReason,
    UpcomingGtfsStop,
)
from scripts.evaluate_eta_replay import _percentile
from scripts.refresh_eta_segment_profiles import _aligned_window_end


def _stop(distance_ahead: float) -> UpcomingGtfsStop:
    return UpcomingGtfsStop(
        stop_id="S1",
        stop_name="Central",
        latitude=-22.9,
        longitude=-43.2,
        stop_sequence=1,
        shape_dist_traveled=distance_ahead,
        shape_distance_ahead=distance_ahead,
    )


def test_geometric_eta_uses_speed_percentiles_and_position_age() -> None:
    observed_at = datetime(2026, 9, 12, 12, tzinfo=UTC)
    evaluated_at = observed_at + timedelta(seconds=10)
    evidence = EtaEvidence(
        method=EtaMethod.VEHICLE_RECENT_SPEED,
        sample_count=5,
        window_seconds=300,
        speed_p25_mps=4,
        speed_median_mps=5,
        speed_p75_mps=10,
    )

    result = estimate_stop_arrivals(
        (_stop(100),),
        evidence=evidence,
        observed_at=observed_at,
        evaluated_at=evaluated_at,
    )[0]

    assert result.estimated_arrival_at == observed_at + timedelta(seconds=20)
    assert result.eta_seconds == 10
    assert result.eta_lower_seconds == 0
    assert result.eta_upper_seconds == 15
    assert result.eta_unavailable_reason is None


def test_geometric_eta_rejects_unbounded_distance() -> None:
    observed_at = datetime(2026, 9, 12, 12, tzinfo=UTC)
    evidence = EtaEvidence(
        method=EtaMethod.ROUTE_SHAPE_RECENT_SPEED,
        sample_count=20,
        window_seconds=600,
        speed_p25_mps=3,
        speed_median_mps=5,
        speed_p75_mps=8,
    )

    result = estimate_stop_arrivals(
        (_stop(20_001),),
        evidence=evidence,
        observed_at=observed_at,
        evaluated_at=observed_at,
    )[0]

    assert result.eta_seconds is None
    assert result.estimated_arrival_at is None
    assert result.eta_unavailable_reason is EtaUnavailableReason.DISTANCE_OUT_OF_RANGE


def test_replay_percentile_uses_linear_interpolation() -> None:
    assert _percentile([], 0.9) is None
    assert _percentile([10, 20, 30, 40], 0.5) == 25
    assert _percentile([10, 20, 30, 40], 0.9) == 37


def test_profile_refresh_uses_only_complete_delayed_windows() -> None:
    now = datetime(2026, 9, 12, 12, 23, 45, tzinfo=UTC)

    assert _aligned_window_end(now, 5) == datetime(2026, 9, 12, 12, 15, tzinfo=UTC)
