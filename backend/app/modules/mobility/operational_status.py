from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.modules.mobility.gtfs.models import JourneyUnavailableReason

FAR_OFF_ROUTE_METRES = 500.0
STATIONARY_SPEED_MPS = 0.5


class CandidateOperationalClass(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    OFF_ROUTE_UNCLASSIFIED = "off_route_unclassified"
    PROBABLE_OUT_OF_SERVICE_STATIONARY = "probable_out_of_service_stationary"
    PROBABLE_DEADHEAD_OR_REPOSITIONING = "probable_deadhead_or_repositioning"
    PROBABLE_OUT_OF_SERVICE_SPEED_UNKNOWN = "probable_out_of_service_speed_unknown"


@dataclass(frozen=True)
class CandidateOperationalAssessment:
    classification: CandidateOperationalClass
    eta_permitted: bool
    reason_codes: tuple[str, ...]


def classify_unmatched_vehicle(
    *,
    unavailable_reason: JourneyUnavailableReason | str | None,
    projection_distance_m: float | None,
    speed_mps: float | None,
) -> CandidateOperationalAssessment:
    """Classify only strong off-route evidence; never manufacture an ETA."""

    reason = str(unavailable_reason or "")
    if reason != JourneyUnavailableReason.VEHICLE_OFF_SHAPE.value:
        return CandidateOperationalAssessment(
            classification=CandidateOperationalClass.NOT_APPLICABLE,
            eta_permitted=False,
            reason_codes=("journey_match_unavailable",),
        )
    if projection_distance_m is None or projection_distance_m < FAR_OFF_ROUTE_METRES:
        return CandidateOperationalAssessment(
            classification=CandidateOperationalClass.OFF_ROUTE_UNCLASSIFIED,
            eta_permitted=False,
            reason_codes=("vehicle_off_shape", "insufficient_operational_evidence"),
        )
    if speed_mps is None:
        classification = CandidateOperationalClass.PROBABLE_OUT_OF_SERVICE_SPEED_UNKNOWN
        speed_reason = "speed_unknown"
    elif speed_mps <= STATIONARY_SPEED_MPS:
        classification = CandidateOperationalClass.PROBABLE_OUT_OF_SERVICE_STATIONARY
        speed_reason = "stationary_or_nearly_stationary"
    else:
        classification = CandidateOperationalClass.PROBABLE_DEADHEAD_OR_REPOSITIONING
        speed_reason = "moving_far_from_route"
    return CandidateOperationalAssessment(
        classification=classification,
        eta_permitted=False,
        reason_codes=("vehicle_far_off_shape", speed_reason),
    )
