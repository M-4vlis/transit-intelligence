from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

_BANDS = ("high", "medium", "low")
_CURRENT_SAMPLING_METHOD = "deterministic_vehicle_hash_v1"
_CURRENT_EVALUATION_SCHEMA_VERSION = 2
_RIO_TZ = ZoneInfo("America/Sao_Paulo")


def _daypart(anchor: datetime) -> str:
    hour = anchor.astimezone(_RIO_TZ).hour
    if 6 <= hour < 10:
        return "morning_peak"
    if 10 <= hour < 16:
        return "interpeak"
    if 16 <= hour < 20:
        return "evening_peak"
    return "night"


def summarize_reports(
    reports: list[dict[str, Any]], *, generated_at: datetime
) -> dict[str, object]:
    unique: dict[str, dict[str, Any]] = {}
    for report in reports:
        anchor = report.get("parameters", {}).get("effective_anchor_at")
        if isinstance(anchor, str):
            unique[anchor] = report

    ordered = sorted(unique.items())
    totals = {
        band: {"outcome_count": 0, "absolute_error_sum": 0.0, "interval_hit_sum": 0.0}
        for band in _BANDS
    }
    versions: set[str] = set()
    sampling_methods: set[str] = set()
    evaluation_schema_versions: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    excluded_reasons: Counter[str] = Counter()
    diagnostic_outcomes = 0
    errors_over_300_seconds = 0
    monotonic_true = 0
    monotonic_evaluated = 0
    calibration_dates: set[str] = set()
    calibration_dayparts: Counter[str] = Counter()
    calibration_band_outcomes: Counter[str] = Counter()
    calibration_cohort_count = 0
    for anchor_text, report in ordered:
        statuses[str(report.get("status", "unknown"))] += 1
        evaluation_schema_version = int(report.get("evaluation_schema_version") or 1)
        evaluation_schema_versions[str(evaluation_schema_version)] += 1
        sampling_method = report.get("parameters", {}).get("sampling_method")
        if isinstance(sampling_method, str):
            sampling_methods.add(sampling_method)
        is_current_sample = (
            sampling_method == _CURRENT_SAMPLING_METHOD
            and evaluation_schema_version == _CURRENT_EVALUATION_SCHEMA_VERSION
        )
        if is_current_sample:
            calibration_cohort_count += 1
            anchor = datetime.fromisoformat(anchor_text)
            local_anchor = anchor.astimezone(_RIO_TZ)
            calibration_dates.add(local_anchor.date().isoformat())
            calibration_dayparts[_daypart(anchor)] += 1
        excluded_reasons.update(report.get("excluded_reasons", {}))
        overall_diagnostics = report.get("diagnostics", {}).get("overall", {})
        diagnostic_outcomes += int(overall_diagnostics.get("outcome_count") or 0)
        errors_over_300_seconds += int(
            overall_diagnostics.get("error_over_300_seconds_count") or 0
        )
        candidate = report.get("candidate_confidence", {})
        version = candidate.get("candidate_version")
        if isinstance(version, str):
            versions.add(version)
        monotonic = candidate.get("monotonic_mae")
        if isinstance(monotonic, bool):
            monotonic_evaluated += 1
            monotonic_true += int(monotonic)
        bands = candidate.get("bands", {})
        for band in _BANDS:
            metrics = bands.get(band, {})
            count = int(metrics.get("outcome_count") or 0)
            mae = metrics.get("mae_seconds")
            coverage = metrics.get("interval_coverage")
            totals[band]["outcome_count"] += count
            if is_current_sample:
                calibration_band_outcomes[band] += count
            if mae is not None:
                totals[band]["absolute_error_sum"] += float(mae) * count
            if coverage is not None:
                totals[band]["interval_hit_sum"] += float(coverage) * count

    band_summary: dict[str, object] = {}
    for band in _BANDS:
        count = int(totals[band]["outcome_count"])
        band_summary[band] = {
            "outcome_count": count,
            "weighted_mae_seconds": (
                round(float(totals[band]["absolute_error_sum"]) / count, 3)
                if count
                else None
            ),
            "weighted_interval_coverage": (
                round(float(totals[band]["interval_hit_sum"]) / count, 4)
                if count
                else None
            ),
        }

    all_dayparts = {"morning_peak", "interpeak", "evening_peak", "night"}
    calibration_coverage = {
        "sampling_method": _CURRENT_SAMPLING_METHOD,
        "evaluation_schema_version": _CURRENT_EVALUATION_SCHEMA_VERSION,
        "cohort_count": calibration_cohort_count,
        "local_dates": sorted(calibration_dates),
        "independent_day_count": len(calibration_dates),
        "daypart_cohorts": {
            name: calibration_dayparts[name] for name in sorted(all_dayparts)
        },
        "band_outcomes": {
            band: calibration_band_outcomes[band] for band in _BANDS
        },
        "seven_day_coverage_met": len(calibration_dates) >= 7,
        "all_dayparts_met": all(calibration_dayparts[name] > 0 for name in all_dayparts),
        "minimum_50_outcomes_per_band_met": all(
            calibration_band_outcomes[band] >= 50 for band in _BANDS
        ),
    }

    return {
        "schema_version": 1,
        "generated_at": generated_at.astimezone(UTC).isoformat(),
        "source_report_count": len(reports),
        "unique_cohort_count": len(ordered),
        "first_anchor_at": ordered[0][0] if ordered else None,
        "last_anchor_at": ordered[-1][0] if ordered else None,
        "candidate_versions": sorted(versions),
        "sampling_methods": sorted(sampling_methods),
        "evaluation_schema_versions": dict(sorted(evaluation_schema_versions.items())),
        "statuses": dict(sorted(statuses.items())),
        "excluded_reasons": dict(sorted(excluded_reasons.items())),
        "total_outcomes": sum(
            int(band_summary[band]["outcome_count"]) for band in _BANDS
        ),
        "diagnostics": {
            "outcome_count": diagnostic_outcomes,
            "error_over_300_seconds_count": errors_over_300_seconds,
            "error_over_300_seconds_rate": (
                round(errors_over_300_seconds / diagnostic_outcomes, 4)
                if diagnostic_outcomes
                else None
            ),
        },
        "monotonic_cohorts": {
            "passed": monotonic_true,
            "evaluated": monotonic_evaluated,
        },
        "calibration_coverage": calibration_coverage,
        "bands": band_summary,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize immutable confidence cohorts")
    parser.add_argument("--reports-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    reports = []
    for path in sorted(args.reports_dir.glob("cohort-*.json")):
        with path.open(encoding="utf-8") as handle:
            reports.append(json.load(handle))
    if not reports:
        raise SystemExit("no cohort reports found")
    print(
        json.dumps(
            summarize_reports(reports, generated_at=datetime.now(UTC)),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
