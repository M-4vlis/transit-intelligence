from datetime import UTC, datetime

from scripts.build_m2_readiness_report import build_readiness_report


def _operations(status: str = "passed") -> dict:
    return {
        "status": status,
        "object_storage_archive": {"missing_files": [], "changed_files": []},
    }


def test_readiness_report_stays_collecting_without_calibration() -> None:
    report = build_readiness_report(
        summary={"outcome_count": 72},
        calibration={
            "status": "insufficient_data",
            "promotion_authorized": False,
            "gates": {"seven_independent_days": False},
            "calibration_candidate": None,
            "coverage": {"independent_day_count": 1},
        },
        operations=_operations(),
        generated_at=datetime(2026, 9, 13, tzinfo=UTC),
        sources={"summary": "s", "calibration": "c", "operations": "o"},
    )

    assert report["status"] == "collecting"
    assert report["promotion_authorized"] is False
    assert report["manual_decision_required"] is True
    assert "all_calibration_gates" in report["blocking_reasons"]


def test_readiness_report_can_only_request_manual_review() -> None:
    report = build_readiness_report(
        summary={"outcome_count": 500},
        calibration={
            "status": "candidate_for_manual_review",
            "promotion_authorized": False,
            "gates": {"coverage": True, "holdout": True},
            "coverage": {"independent_day_count": 9},
            "calibration_candidate": {
                "heldout_monotonic_mae": True,
                "heldout_interval_coverage": {
                    "high": 0.8,
                    "medium": 0.75,
                    "low": 0.72,
                },
            },
        },
        operations=_operations(),
        generated_at=datetime(2026, 9, 13, tzinfo=UTC),
        sources={"summary": "s", "calibration": "c", "operations": "o"},
    )

    assert report["status"] == "candidate_for_manual_review"
    assert report["blocking_reasons"] == []
    assert report["promotion_authorized"] is False
