from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.mobility.confidence import (
    CANDIDATE_CONFIDENCE_VERSION,
    CandidateConfidence,
    CandidateConfidenceBand,
)

SHADOW_CONFIDENCE_CONTRACT_VERSION = "m2-shadow-v2"


class ShadowExposure(StrEnum):
    INTERNAL_ONLY = "internal_only"


class ConfidencePublicationState(StrEnum):
    WITHHELD_UNCALIBRATED = "withheld_uncalibrated"
    WITHHELD_PENDING_MANUAL_REVIEW = "withheld_pending_manual_review"


class ArrivalWindowSource(StrEnum):
    ETA_NATIVE = "eta_native"
    CALIBRATED_CANDIDATE = "calibrated_candidate"


class ArrivalWindowSeconds(BaseModel):
    model_config = ConfigDict(frozen=True)

    estimated: int = Field(ge=0)
    lower: int = Field(ge=0)
    upper: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_order(self) -> ArrivalWindowSeconds:
        if not self.lower <= self.estimated <= self.upper:
            raise ValueError("arrival window must contain the estimate")
        return self


class ShadowConfidenceContract(BaseModel):
    """Versioned internal contract; deliberately impossible to publish."""

    model_config = ConfigDict(frozen=True)

    contract_version: str = SHADOW_CONFIDENCE_CONTRACT_VERSION
    exposure: ShadowExposure = ShadowExposure.INTERNAL_ONLY
    publishable: bool = False
    publication_state: ConfidencePublicationState
    candidate_algorithm_version: str = CANDIDATE_CONFIDENCE_VERSION
    candidate_level: CandidateConfidenceBand
    candidate_score: int = Field(ge=0, le=100)
    arrival_window_seconds: ArrivalWindowSeconds | None
    arrival_window_source: ArrivalWindowSource | None
    reason_codes: tuple[str, ...]

    @model_validator(mode="after")
    def reject_publication(self) -> ShadowConfidenceContract:
        if self.publishable:
            raise ValueError("shadow confidence contract cannot be publishable")
        if (self.arrival_window_seconds is None) != (self.arrival_window_source is None):
            raise ValueError("arrival window and source must be present together")
        return self


def build_shadow_confidence_contract(
    *,
    candidate: CandidateConfidence,
    calibration_status: str,
    estimated_eta_seconds: int | None,
    lower_eta_seconds: int | None,
    upper_eta_seconds: int | None,
    calibrated_offsets_seconds: tuple[float, float] | None = None,
) -> ShadowConfidenceContract:
    state = (
        ConfidencePublicationState.WITHHELD_PENDING_MANUAL_REVIEW
        if calibration_status == "candidate_for_manual_review"
        else ConfidencePublicationState.WITHHELD_UNCALIBRATED
    )
    source = None
    window = None
    if estimated_eta_seconds is not None and calibrated_offsets_seconds is not None:
        estimate = int(estimated_eta_seconds)
        lower_offset, upper_offset = calibrated_offsets_seconds
        calibrated_lower = round(estimate + lower_offset)
        calibrated_upper = round(estimate + upper_offset)
        window = ArrivalWindowSeconds(
            estimated=estimate,
            lower=max(0, min(estimate, calibrated_lower)),
            upper=max(estimate, calibrated_upper),
        )
        source = ArrivalWindowSource.CALIBRATED_CANDIDATE
    elif all(
        value is not None
        for value in (estimated_eta_seconds, lower_eta_seconds, upper_eta_seconds)
    ):
        window = ArrivalWindowSeconds(
            estimated=int(estimated_eta_seconds),
            lower=int(lower_eta_seconds),
            upper=int(upper_eta_seconds),
        )
        source = ArrivalWindowSource.ETA_NATIVE
    reasons = (
        *candidate.reasons,
        *(('calibrated_arrival_window',) if calibrated_offsets_seconds else ()),
        state.value,
    )
    return ShadowConfidenceContract(
        publication_state=state,
        candidate_level=candidate.band,
        candidate_score=candidate.score,
        arrival_window_seconds=window,
        arrival_window_source=source,
        reason_codes=reasons,
    )
