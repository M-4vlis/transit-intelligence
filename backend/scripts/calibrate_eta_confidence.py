from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from math import floor
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

_BANDS = ("high", "medium", "low")
_SAMPLING_METHOD = "deterministic_vehicle_hash_v1"
_EVALUATION_SCHEMA_VERSION = 2
_OBSERVATION_SCHEMA_VERSION = 1
_RIO_TZ = ZoneInfo("America/Sao_Paulo")


def _percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * quantile
    lower = floor(index)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = index - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _daypart(anchor: datetime) -> str:
    hour = anchor.astimezone(_RIO_TZ).hour
    if 6 <= hour < 10:
        return "morning_peak"
    if 10 <= hour < 16:
        return "interpeak"
    if 16 <= hour < 20:
        return "evening_peak"
    return "night"


def _eligible_reports(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[str, dict[str, Any]] = {}
    for report in reports:
        parameters = report.get("parameters", {})
        anchor = parameters.get("effective_anchor_at")
        if (
            isinstance(anchor, str)
            and report.get("evaluation_schema_version") == _EVALUATION_SCHEMA_VERSION
            and report.get("calibration_observation_schema_version")
            == _OBSERVATION_SCHEMA_VERSION
            and parameters.get("sampling_method") == _SAMPLING_METHOD
        ):
            unique[anchor] = report
    return [unique[anchor] for anchor in sorted(unique)]


def _observations(
    reports: list[dict[str, Any]],
) -> list[tuple[str, str, dict[str, Any]]]:
    result = []
    for report in _eligible_reports(reports):
        anchor_text = report["parameters"]["effective_anchor_at"]
        anchor = datetime.fromisoformat(anchor_text)
        local_date = anchor.astimezone(_RIO_TZ).date().isoformat()
        daypart = _daypart(anchor)
        for observation in report.get("calibration_observations", []):
            if isinstance(observation, dict):
                result.append((local_date, daypart, observation))
    return result


def _band_metrics(observations: list[dict[str, Any]]) -> dict[str, object]:
    signed_errors = [float(item["signed_error_seconds"]) for item in observations]
    absolute_errors = [abs(value) for value in signed_errors]
    residuals = [-value for value in signed_errors]
    count = len(observations)
    return {
        "outcome_count": count,
        "mae_seconds": (
            round(sum(absolute_errors) / count, 3) if count else None
        ),
        "error_p90_seconds": (
            round(value, 3)
            if (value := _percentile(absolute_errors, 0.9)) is not None
            else None
        ),
        "actual_minus_predicted_p10_seconds": (
            round(value, 3)
            if (value := _percentile(residuals, 0.1)) is not None
            else None
        ),
        "actual_minus_predicted_p90_seconds": (
            round(value, 3)
            if (value := _percentile(residuals, 0.9)) is not None
            else None
        ),
    }


def build_calibration_report(
    reports: list[dict[str, Any]], *, generated_at: datetime
) -> dict[str, object]:
    eligible_reports = _eligible_reports(reports)
    observations = _observations(reports)
    dates = sorted({date for date, _, _ in observations})
    dayparts = Counter(daypart for _, daypart, _ in observations)
    bands = Counter(str(item.get("candidate_band")) for _, _, item in observations)
    methods = Counter(str(item.get("eta_method")) for _, _, item in observations)
    routes = Counter(str(item.get("route_id")) for _, _, item in observations)
    outcome_count = len(observations)
    maximum_route_share = max(routes.values(), default=0) / outcome_count if outcome_count else 0
    all_dayparts = {"morning_peak", "interpeak", "evening_peak", "night"}
    gates = {
        "seven_independent_days": len(dates) >= 7,
        "all_dayparts": all(dayparts[name] > 0 for name in all_dayparts),
        "minimum_50_outcomes_per_band": all(bands[band] >= 50 for band in _BANDS),
        "maximum_single_route_share_20_percent": maximum_route_share <= 0.2,
    }
    result: dict[str, object] = {
        "schema_version": 1,
        "generated_at": generated_at.astimezone(UTC).isoformat(),
        "status": "insufficient_data",
        "promotion_authorized": False,
        "source": {
            "sampling_method": _SAMPLING_METHOD,
            "evaluation_schema_version": _EVALUATION_SCHEMA_VERSION,
            "observation_schema_version": _OBSERVATION_SCHEMA_VERSION,
            "eligible_cohort_count": len(eligible_reports),
        },
        "coverage": {
            "outcome_count": outcome_count,
            "local_dates": dates,
            "independent_day_count": len(dates),
            "daypart_outcomes": {
                name: dayparts[name] for name in sorted(all_dayparts)
            },
            "band_outcomes": {band: bands[band] for band in _BANDS},
            "eta_methods": dict(sorted(methods.items())),
            "route_count": len(routes),
            "maximum_single_route_share": round(maximum_route_share, 4),
        },
        "gates": gates,
        "calibration_candidate": None,
    }
    if not all(gates.values()):
        return result

    heldout_dates = set(dates[-2:])
    training = [item for date, _, item in observations if date not in heldout_dates]
    heldout = [item for date, _, item in observations if date in heldout_dates]
    training_bands = {
        band: [item for item in training if item.get("candidate_band") == band]
        for band in _BANDS
    }
    heldout_bands = {
        band: [item for item in heldout if item.get("candidate_band") == band]
        for band in _BANDS
    }
    training_minimum_met = all(len(training_bands[band]) >= 30 for band in _BANDS)
    heldout_minimum_met = all(len(heldout_bands[band]) >= 20 for band in _BANDS)
    result["gates"] = {
        **gates,
        "minimum_30_training_per_band": training_minimum_met,
        "minimum_20_heldout_per_band": heldout_minimum_met,
    }
    if not training_minimum_met or not heldout_minimum_met:
        return result

    interval_offsets = {
        band: {
            "lower_seconds": _band_metrics(training_bands[band])[
                "actual_minus_predicted_p10_seconds"
            ],
            "upper_seconds": _band_metrics(training_bands[band])[
                "actual_minus_predicted_p90_seconds"
            ],
        }
        for band in _BANDS
    }
    heldout_coverage = {}
    for band in _BANDS:
        offsets = interval_offsets[band]
        lower = float(offsets["lower_seconds"])
        upper = float(offsets["upper_seconds"])
        residuals = [
            -float(item["signed_error_seconds"]) for item in heldout_bands[band]
        ]
        heldout_coverage[band] = round(
            sum(lower <= value <= upper for value in residuals) / len(residuals),
            4,
        )

    heldout_metrics = {
        band: _band_metrics(heldout_bands[band]) for band in _BANDS
    }
    monotonic_heldout_mae = (
        heldout_metrics["high"]["mae_seconds"]
        <= heldout_metrics["medium"]["mae_seconds"]
        <= heldout_metrics["low"]["mae_seconds"]
    )
    result["status"] = "candidate_for_manual_review"
    result["calibration_candidate"] = {
        "training_dates": [date for date in dates if date not in heldout_dates],
        "heldout_dates": sorted(heldout_dates),
        "training_band_metrics": {
            band: _band_metrics(training_bands[band]) for band in _BANDS
        },
        "heldout_band_metrics": heldout_metrics,
        "proposed_interval_offsets_seconds": interval_offsets,
        "heldout_interval_coverage": heldout_coverage,
        "heldout_monotonic_mae": monotonic_heldout_mae,
    }
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a guarded offline ETA confidence calibration report"
    )
    parser.add_argument("--reports-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    reports = []
    for path in sorted(args.reports_dir.glob("cohort-*.json")):
        with path.open(encoding="utf-8") as handle:
            reports.append(json.load(handle))
    print(
        json.dumps(
            build_calibration_report(reports, generated_at=datetime.now(UTC)),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
