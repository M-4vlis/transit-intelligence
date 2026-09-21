from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.modules.mobility.gtfs.models import EtaEvidence, EtaMethod, JourneyMatchMethod

CANDIDATE_CONFIDENCE_VERSION = "m2-candidate-v4"
_HIGH_BAND_MINIMUM = 79
_MEDIUM_BAND_MINIMUM = 65


class CandidateConfidenceBand(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class CandidateConfidence:
    score: int
    band: CandidateConfidenceBand
    components: dict[str, int]
    reasons: tuple[str, ...]


def _recency_score(position_age_seconds: float) -> int:
    if position_age_seconds <= 15:
        return 25
    if position_age_seconds <= 30:
        return 20
    if position_age_seconds <= 60:
        return 12
    return 5


def _projection_score(projection_distance_m: float) -> int:
    if projection_distance_m <= 25:
        return 20
    if projection_distance_m <= 75:
        return 15
    if projection_distance_m <= 150:
        return 8
    return 2


def _sample_score(evidence: EtaEvidence) -> int:
    thresholds = {
        EtaMethod.VEHICLE_RECENT_SPEED: (10, 5),
        EtaMethod.HISTORICAL_SEGMENT_TIME_BAND: (500, 200),
        EtaMethod.ROUTE_SHAPE_RECENT_SPEED: (100, 50),
    }
    strong, moderate = thresholds[evidence.method]
    if evidence.sample_count >= strong:
        return 20
    if evidence.sample_count >= moderate:
        return 14
    return 8


def _dispersion_score(evidence: EtaEvidence) -> tuple[int, float]:
    spread_ratio = max(
        0.0,
        (evidence.speed_p75_mps - evidence.speed_p25_mps)
        / evidence.speed_median_mps,
    )
    if spread_ratio <= 0.25:
        return 20, spread_ratio
    if spread_ratio <= 0.5:
        return 13, spread_ratio
    if spread_ratio <= 1.0:
        return 7, spread_ratio
    return 0, spread_ratio


def _horizon_penalty(predicted_eta_seconds: float) -> int:
    """Penalize uncertainty growth without encoding the ETA method itself."""

    if predicted_eta_seconds <= 180:
        return 0
    if predicted_eta_seconds <= 360:
        return 10
    if predicted_eta_seconds <= 600:
        return 20
    return 30


def assess_candidate_confidence(
    *,
    evidence: EtaEvidence,
    position_age_seconds: float,
    projection_distance_m: float,
    match_method: JourneyMatchMethod | None,
    predicted_eta_seconds: float,
) -> CandidateConfidence:
    """Produce an internal, explicitly uncalibrated confidence candidate."""

    dispersion, spread_ratio = _dispersion_score(evidence)
    components = {
        "position_recency": _recency_score(position_age_seconds),
        "shape_projection": _projection_score(projection_distance_m),
        "sample_support": _sample_score(evidence),
        "speed_dispersion": dispersion,
        "journey_match": 15 if match_method is JourneyMatchMethod.EXACT_TRIP else 5,
    }
    horizon_penalty = _horizon_penalty(predicted_eta_seconds)
    components["prediction_horizon_penalty"] = -horizon_penalty
    score = max(0, min(100, sum(components.values())))
    band = (
        CandidateConfidenceBand.HIGH
        if score >= _HIGH_BAND_MINIMUM
        else CandidateConfidenceBand.MEDIUM
        if score >= _MEDIUM_BAND_MINIMUM
        else CandidateConfidenceBand.LOW
    )
    reasons: list[str] = []
    if position_age_seconds > 30:
        reasons.append("position_older_than_30s")
    if projection_distance_m > 75:
        reasons.append("projection_over_75m")
    if evidence.method is not EtaMethod.VEHICLE_RECENT_SPEED:
        reasons.append("fallback_speed_evidence")
    if spread_ratio > 0.5:
        reasons.append("high_speed_dispersion")
    if match_method is not JourneyMatchMethod.EXACT_TRIP:
        reasons.append("route_shape_pattern_match")
    if horizon_penalty:
        reasons.append(
            "eta_horizon_over_10m"
            if predicted_eta_seconds > 600
            else "eta_horizon_over_6m"
            if predicted_eta_seconds > 360
            else "eta_horizon_over_3m"
        )
    return CandidateConfidence(
        score=score,
        band=band,
        components=components,
        reasons=tuple(reasons),
    )
