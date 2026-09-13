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
    assert summary["evaluation_schema_versions"] == {"1": 2}
    assert summary["calibration_coverage"] == {
        "sampling_method": "deterministic_vehicle_hash_v1",
        "evaluation_schema_version": 2,
        "cohort_count": 0,
        "local_dates": [],
        "independent_day_count": 0,
        "daypart_cohorts": {
            "evening_peak": 0,
            "interpeak": 0,
            "morning_peak": 0,
            "night": 0,
        },
        "band_outcomes": {"high": 0, "medium": 0, "low": 0},
        "seven_day_coverage_met": False,
        "all_dayparts_met": False,
        "minimum_50_outcomes_per_band_met": False,
    }


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


def test_confidence_summary_tracks_rio_dayparts_for_current_sampling() -> None:
    anchors = (
        "2026-09-13T10:00:00+00:00",
        "2026-09-13T15:00:00+00:00",
        "2026-09-13T20:00:00+00:00",
        "2026-09-15T02:00:00+00:00",
    )
    reports = []
    for anchor in anchors:
        report = _report(
            anchor,
            high=(20, 20, 0.8),
            medium=(20, 40, 0.6),
            low=(20, 100, 0.2),
            monotonic=True,
        )
        report["parameters"]["sampling_method"] = (
            "deterministic_vehicle_hash_v1"
        )
        report["evaluation_schema_version"] = 2
        reports.append(report)

    summary = summarize_reports(
        reports, generated_at=datetime(2026, 9, 14, 3, tzinfo=UTC)
    )
    coverage = summary["calibration_coverage"]

    assert coverage["cohort_count"] == 4
    assert coverage["independent_day_count"] == 2
    assert coverage["daypart_cohorts"] == {
        "evening_peak": 1,
        "interpeak": 1,
        "morning_peak": 1,
        "night": 1,
    }
    assert coverage["minimum_50_outcomes_per_band_met"] is True
    assert coverage["all_dayparts_met"] is True
    assert coverage["seven_day_coverage_met"] is False


def test_confidence_summary_excludes_legacy_timebase_from_calibration() -> None:
    report = _report(
        "2026-09-13T10:00:00+00:00",
        high=(100, 20, 0.8),
        medium=(100, 40, 0.6),
        low=(100, 100, 0.2),
        monotonic=True,
    )
    report["parameters"]["sampling_method"] = "deterministic_vehicle_hash_v1"

    summary = summarize_reports(
        [report], generated_at=datetime(2026, 9, 13, 11, tzinfo=UTC)
    )

    assert summary["evaluation_schema_versions"] == {"1": 1}
    assert summary["calibration_coverage"]["cohort_count"] == 0
    assert summary["calibration_coverage"]["band_outcomes"] == {
        "high": 0,
        "medium": 0,
        "low": 0,
    }
