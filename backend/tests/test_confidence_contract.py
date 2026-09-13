from app.modules.mobility.confidence import CandidateConfidence, CandidateConfidenceBand
from app.modules.mobility.confidence_contract import (
    SHADOW_CONFIDENCE_CONTRACT_VERSION,
    ConfidencePublicationState,
    ShadowConfidenceContract,
    build_shadow_confidence_contract,
)


def test_shadow_contract_is_versioned_and_fail_closed() -> None:
    contract = build_shadow_confidence_contract(
        candidate=CandidateConfidence(
            score=91,
            band=CandidateConfidenceBand.HIGH,
            components={"position_recency": 25},
            reasons=(),
        ),
        calibration_status="uncalibrated",
        estimated_eta_seconds=120,
        lower_eta_seconds=90,
        upper_eta_seconds=180,
    )

    assert contract.contract_version == SHADOW_CONFIDENCE_CONTRACT_VERSION
    assert contract.publishable is False
    assert contract.publication_state is (
        ConfidencePublicationState.WITHHELD_UNCALIBRATED
    )
    assert contract.arrival_window_seconds is not None
    assert contract.arrival_window_seconds.lower == 90
    assert contract.reason_codes == ("withheld_uncalibrated",)


def test_shadow_contract_cannot_be_marked_publishable() -> None:
    try:
        ShadowConfidenceContract(
            publishable=True,
            publication_state="withheld_uncalibrated",
            candidate_level="low",
            candidate_score=10,
            arrival_window_seconds=None,
            reason_codes=("withheld_uncalibrated",),
        )
    except ValueError as exc:
        assert "cannot be publishable" in str(exc)
    else:
        raise AssertionError("shadow contract accepted publishable=true")
