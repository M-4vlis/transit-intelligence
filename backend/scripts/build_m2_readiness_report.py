from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_MINIMUM_HELDOUT_INTERVAL_COVERAGE = 0.70
_MAXIMUM_HIGH_ERROR_OVER_300_RATE = 0.10


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def _source_name(path: Path) -> str:
    return path.resolve().name if path.is_symlink() else path.name


def build_readiness_report(
    *,
    summary: dict[str, Any],
    calibration: dict[str, Any],
    operations: dict[str, Any],
    generated_at: datetime,
    sources: dict[str, str],
) -> dict[str, object]:
    gates = calibration.get("gates", {})
    calibration_candidate = calibration.get("calibration_candidate")
    heldout_monotonic = bool(
        calibration_candidate
        and calibration_candidate.get("heldout_monotonic_mae") is True
    )
    heldout_p90_monotonic = bool(
        calibration_candidate
        and calibration_candidate.get("heldout_monotonic_p90") is True
    )
    heldout_coverage = (
        calibration_candidate.get("heldout_interval_coverage", {})
        if calibration_candidate
        else {}
    )
    coverage_sufficient = bool(
        heldout_coverage
        and all(
            float(value) >= _MINIMUM_HELDOUT_INTERVAL_COVERAGE
            for value in heldout_coverage.values()
        )
    )
    heldout_metrics = (
        calibration_candidate.get("heldout_band_metrics", {})
        if calibration_candidate
        else {}
    )
    high_tail_rate = heldout_metrics.get("high", {}).get(
        "error_over_300_seconds_rate"
    )
    high_tail_sufficient = bool(
        high_tail_rate is not None
        and float(high_tail_rate) <= _MAXIMUM_HIGH_ERROR_OVER_300_RATE
    )
    archive = operations.get("object_storage_archive", {})
    checks = {
        "operations_healthy": operations.get("status") != "failed",
        "all_calibration_gates": bool(gates) and all(bool(value) for value in gates.values()),
        "calibration_candidate_exists": calibration.get("status")
        == "candidate_for_manual_review"
        and calibration_candidate is not None,
        "heldout_mae_is_monotonic": heldout_monotonic,
        "heldout_p90_is_monotonic": heldout_p90_monotonic,
        "heldout_interval_coverage_at_least_70_percent": coverage_sufficient,
        "heldout_high_error_over_300_at_most_10_percent": high_tail_sufficient,
        "object_storage_archive_complete": not archive.get("missing_files")
        and not archive.get("changed_files"),
        "automatic_promotion_disabled": calibration.get("promotion_authorized") is False,
    }
    blocking = [name for name, passed in checks.items() if not passed]
    if not checks["operations_healthy"]:
        status = "blocked_operational"
    elif calibration.get("status") == "insufficient_data":
        status = "collecting"
    elif blocking:
        status = "candidate_rejected"
    else:
        status = "candidate_for_manual_review"
    return {
        "schema_version": 1,
        "generated_at": generated_at.astimezone(UTC).isoformat(),
        "status": status,
        "promotion_authorized": False,
        "manual_decision_required": True,
        "sources": sources,
        "checks": checks,
        "blocking_reasons": blocking,
        "coverage": calibration.get("coverage", {}),
        "calibration_status": calibration.get("status"),
        "calibration_candidate": calibration_candidate,
        "operations_status": operations.get("status"),
        "summary": {
            "eligible_cohort_count": summary.get("eligible_cohort_count"),
            "outcome_count": summary.get("outcome_count"),
            "calibration_coverage": summary.get("calibration_coverage"),
        },
        "policy": {
            "minimum_heldout_interval_coverage": (
                _MINIMUM_HELDOUT_INTERVAL_COVERAGE
            ),
            "maximum_heldout_high_error_over_300_rate": (
                _MAXIMUM_HIGH_ERROR_OVER_300_RATE
            ),
            "public_contract_requires_separate_manual_decision": True,
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the guarded M2 readiness report")
    parser.add_argument("--reports-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    paths = {
        "summary": args.reports_dir / "summary-latest.json",
        "calibration": args.reports_dir / "calibration-latest.json",
        "operations": args.reports_dir / "operations-latest.json",
    }
    report = build_readiness_report(
        summary=_read_json(paths["summary"]),
        calibration=_read_json(paths["calibration"]),
        operations=_read_json(paths["operations"]),
        generated_at=datetime.now(UTC),
        sources={name: _source_name(path) for name, path in paths.items()},
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
