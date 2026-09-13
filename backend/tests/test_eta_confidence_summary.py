from datetime import UTC, datetime

from scripts.summarize_eta_confidence_cohorts import summarize_reports


def _report(
    anchor: str,
    *,
    high: tuple[int, float, float],
    medium: tuple[int, float, float],
    low: tuple[int, float, float],
    monotonic: bool,
) -> dict:
    bands = {}
    for name, values in (("high", high), ("medium", medium), ("low", low)):
        count, mae, coverage = values
        bands[name] = {
            "outcome_count": count,
            "mae_seconds": mae,
            "interval_coverage": coverage,
        }
    return {
        "status": "sufficient_data",
        "parameters": {"effective_anchor_at": anchor},
        "candidate_confidence": {
            "candidate_version": "m2-candidate-v2",
            "monotonic_mae": monotonic,
            "bands": bands,
        },
    }


def test_confidence_summary_deduplicates_anchors_and_weights_metrics() -> None:
    first = _report(
        "2026-09-13T00:00:00+00:00",
        high=(10, 20, 0.8),
        medium=(20, 40, 0.6),
        low=(5, 100, 0.2),
        monotonic=True,
    )
    second = _report(
        "2026-09-13T03:00:00+00:00",
        high=(30, 40, 0.6),
        medium=(10, 80, 0.4),
        low=(5, 200, 0.0),
        monotonic=False,
    )

    summary = summarize_reports(
        [first, first, second], generated_at=datetime(2026, 9, 13, 4, tzinfo=UTC)
    )

    assert summary["source_report_count"] == 3
    assert summary["unique_cohort_count"] == 2
    assert summary["total_outcomes"] == 80
    assert summary["bands"]["high"]["weighted_mae_seconds"] == 35
    assert summary["bands"]["high"]["weighted_interval_coverage"] == 0.65
    assert summary["monotonic_cohorts"] == {"passed": 1, "evaluated": 2}
    assert summary["candidate_versions"] == ["m2-candidate-v2"]
    assert summary["sampling_methods"] == []


def test_confidence_summary_accumulates_exclusions_and_extreme_errors() -> None:
    report = _report(
        "2026-09-13T06:00:00+00:00",
        high=(10, 20, 0.8),
        medium=(20, 40, 0.6),
        low=(5, 100, 0.2),
        monotonic=True,
    )
    report["excluded_reasons"] = {"vehicle_off_shape": 12}
    report["diagnostics"] = {
        "overall": {
            "outcome_count": 35,
            "error_over_300_seconds_count": 7,
        }
    }

    summary = summarize_reports(
        [report], generated_at=datetime(2026, 9, 13, 7, tzinfo=UTC)
    )

    assert summary["excluded_reasons"] == {"vehicle_off_shape": 12}
    assert summary["diagnostics"] == {
        "outcome_count": 35,
        "error_over_300_seconds_count": 7,
        "error_over_300_seconds_rate": 0.2,
    }
