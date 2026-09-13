from app.modules.mobility.gtfs.models import JourneyUnavailableReason
from app.modules.mobility.operational_status import (
    CandidateOperationalClass,
    classify_unmatched_vehicle,
)


def test_far_stopped_off_shape_vehicle_is_probable_out_of_service() -> None:
    assessment = classify_unmatched_vehicle(
        unavailable_reason=JourneyUnavailableReason.VEHICLE_OFF_SHAPE,
        projection_distance_m=850,
        speed_mps=0.2,
    )

    assert assessment.classification is (
        CandidateOperationalClass.PROBABLE_OUT_OF_SERVICE_STATIONARY
    )
    assert assessment.eta_permitted is False
    assert "stationary_or_nearly_stationary" in assessment.reason_codes


def test_far_moving_off_shape_vehicle_is_probable_repositioning() -> None:
    assessment = classify_unmatched_vehicle(
        unavailable_reason="vehicle_off_shape",
        projection_distance_m=700,
        speed_mps=4.0,
    )

    assert assessment.classification is (
        CandidateOperationalClass.PROBABLE_DEADHEAD_OR_REPOSITIONING
    )
    assert assessment.eta_permitted is False


def test_weak_or_unrelated_evidence_stays_unclassified() -> None:
    near = classify_unmatched_vehicle(
        unavailable_reason="vehicle_off_shape",
        projection_distance_m=300,
        speed_mps=0.0,
    )
    other = classify_unmatched_vehicle(
        unavailable_reason="missing_shape_id",
        projection_distance_m=None,
        speed_mps=None,
    )

    assert near.classification is CandidateOperationalClass.OFF_ROUTE_UNCLASSIFIED
    assert other.classification is CandidateOperationalClass.NOT_APPLICABLE
    assert near.eta_permitted is other.eta_permitted is False
