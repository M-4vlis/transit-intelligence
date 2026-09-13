from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_BANDS = ("high", "medium", "low")


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
    statuses: Counter[str] = Counter()
    excluded_reasons: Counter[str] = Counter()
    diagnostic_outcomes = 0
    errors_over_300_seconds = 0
    monotonic_true = 0
    monotonic_evaluated = 0
    for _, report in ordered:
        statuses[str(report.get("status", "unknown"))] += 1
        sampling_method = report.get("parameters", {}).get("sampling_method")
        if isinstance(sampling_method, str):
            sampling_methods.add(sampling_method)
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

    return {
        "schema_version": 1,
        "generated_at": generated_at.astimezone(UTC).isoformat(),
        "source_report_count": len(reports),
        "unique_cohort_count": len(ordered),
        "first_anchor_at": ordered[0][0] if ordered else None,
        "last_anchor_at": ordered[-1][0] if ordered else None,
        "candidate_versions": sorted(versions),
        "sampling_methods": sorted(sampling_methods),
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
