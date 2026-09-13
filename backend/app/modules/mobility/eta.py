from __future__ import annotations

from datetime import datetime, timedelta
from math import ceil

from app.modules.mobility.gtfs.models import (
    EtaEvidence,
    EtaUnavailableReason,
    UpcomingGtfsStop,
)

MAX_POSITION_AGE_SECONDS = 90
MAX_ETA_DISTANCE_METERS = 20_000


def estimate_stop_arrivals(
    stops: tuple[UpcomingGtfsStop, ...],
    *,
    evidence: EtaEvidence,
    observed_at: datetime,
    evaluated_at: datetime,
) -> tuple[UpcomingGtfsStop, ...]:
    position_age = max(0.0, (evaluated_at - observed_at).total_seconds())
    estimated: list[UpcomingGtfsStop] = []
    for stop in stops:
        if stop.shape_distance_ahead > MAX_ETA_DISTANCE_METERS:
            estimated.append(
                stop.model_copy(
                    update={
                        "eta_unavailable_reason": EtaUnavailableReason.DISTANCE_OUT_OF_RANGE
                    }
                )
            )
            continue

        travel_seconds = stop.shape_distance_ahead / evidence.speed_median_mps
        lower_travel_seconds = stop.shape_distance_ahead / evidence.speed_p75_mps
        upper_travel_seconds = stop.shape_distance_ahead / evidence.speed_p25_mps
        remaining_seconds = max(0, ceil(travel_seconds - position_age))
        estimated.append(
            stop.model_copy(
                update={
                    "estimated_arrival_at": evaluated_at
                    + timedelta(seconds=remaining_seconds),
                    "eta_seconds": remaining_seconds,
                    "eta_lower_seconds": max(0, ceil(lower_travel_seconds - position_age)),
                    "eta_upper_seconds": max(0, ceil(upper_travel_seconds - position_age)),
                }
            )
        )
    return tuple(estimated)
