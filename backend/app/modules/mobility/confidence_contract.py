from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.mobility.confidence import (
    CANDIDATE_CONFIDENCE_VERSION,
    CandidateConfidence,
    CandidateConfidenceBand,
)

SHADOW_CONFIDENCE_CONTRACT_VERSION = "m2-shadow-v1"


class ShadowExposure(StrEnum):
    INTERNAL_ONLY = "internal_only"


class ConfidencePublicationState(StrEnum):
    WITHHELD_UNCALIBRATED = "withheld_uncalibrated"
    WITHHELD_PENDING_MANUAL_REVIEW = "withheld_pending_manual_review"


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
    reason_codes: tuple[str, ...]

    @model_validator(mode="after")
    def reject_publication(self) -> ShadowConfidenceContract:
        if self.publishable:
            raise ValueError("shadow confidence contract cannot be publishable")
        return self


def build_shadow_confidence_contract(
    *,
    candidate: CandidateConfidence,
    calibration_status: str,
    estimated_eta_seconds: int | None,
    lower_eta_seconds: int | None,
    upper_eta_seconds: int | None,
) -> ShadowConfidenceContract:
    state = (
        ConfidencePublicationState.WITHHELD_PENDING_MANUAL_REVIEW
        if calibration_status == "candidate_for_manual_review"
        else ConfidencePublicationState.WITHHELD_UNCALIBRATED
    )
    values = (estimated_eta_seconds, lower_eta_seconds, upper_eta_seconds)
    window = None
    if all(value is not None for value in values):
        window = ArrivalWindowSeconds(
            estimated=int(estimated_eta_seconds),
            lower=int(lower_eta_seconds),
            upper=int(upper_eta_seconds),
        )
    reasons = (*candidate.reasons, state.value)
    return ShadowConfidenceContract(
        publication_state=state,
        candidate_level=candidate.band,
        candidate_score=candidate.score,
        arrival_window_seconds=window,
        reason_codes=reasons,
    )
