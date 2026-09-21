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
_OBSERVATION_SCHEMA_VERSION = 3
_CANDIDATE_VERSION = "m2-candidate-v4"
_RIO_TZ = ZoneInfo("America/Sao_Paulo")
_MAXIMUM_ROUTE_SHARE = 0.20
_MAXIMUM_SPATIAL_CELL_SHARE = 0.50
_MAXIMUM_ETA_METHOD_SHARE = 0.95
_MINIMUM_ROUTES_PER_BAND = 10
_MINIMUM_SPATIAL_CELLS_PER_BAND = 3
_MINIMUM_INDEPENDENT_DAYS = 14
_HOLDOUT_DAY_COUNT = 3
_MINIMUM_DAILY_BAND_OUTCOMES = 10
_MINIMUM_MONOTONIC_DAY_RATE = 0.70


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
            and report.get("candidate_confidence", {}).get("candidate_version")
            == _CANDIDATE_VERSION
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
    error_over_300_count = sum(value > 300 for value in absolute_errors)
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
        "error_over_300_seconds_count": error_over_300_count,
        "error_over_300_seconds_rate": (
            round(error_over_300_count / count, 4) if count else None
        ),
    }


def _daily_stability(
    observations: list[tuple[str, str, dict[str, Any]]],
) -> dict[str, object]:
    dates = sorted({date for date, _, _ in observations})
    eligible = 0
    monotonic_mae = 0
    monotonic_p90 = 0
    daily: dict[str, object] = {}
    for date in dates:
        bands = {
            band: [
                item
                for item_date, _, item in observations
                if item_date == date and item.get("candidate_band") == band
            ]
            for band in _BANDS
        }
        metrics = {band: _band_metrics(bands[band]) for band in _BANDS}
        day_eligible = all(
            len(bands[band]) >= _MINIMUM_DAILY_BAND_OUTCOMES for band in _BANDS
        )
        mae_passed = bool(
            day_eligible
            and metrics["high"]["mae_seconds"]
            <= metrics["medium"]["mae_seconds"]
            <= metrics["low"]["mae_seconds"]
        )
        p90_passed = bool(
            day_eligible
            and metrics["high"]["error_p90_seconds"]
            <= metrics["medium"]["error_p90_seconds"]
            <= metrics["low"]["error_p90_seconds"]
        )
        eligible += int(day_eligible)
        monotonic_mae += int(mae_passed)
        monotonic_p90 += int(p90_passed)
        daily[date] = {
            "eligible": day_eligible,
            "monotonic_mae": mae_passed,
            "monotonic_p90": p90_passed,
            "band_outcomes": {band: len(bands[band]) for band in _BANDS},
        }
    return {
        "minimum_band_outcomes_per_day": _MINIMUM_DAILY_BAND_OUTCOMES,
        "eligible_day_count": eligible,
        "monotonic_mae_day_count": monotonic_mae,
        "monotonic_p90_day_count": monotonic_p90,
        "monotonic_mae_day_rate": round(monotonic_mae / eligible, 4) if eligible else 0,
        "monotonic_p90_day_rate": round(monotonic_p90 / eligible, 4) if eligible else 0,
        "days": daily,
    }


def _share(counts: Counter[str], total: int) -> float:
    return max(counts.values(), default=0) / total if total else 0


def _band_diversity(observations: list[dict[str, Any]]) -> dict[str, object]:
    total = len(observations)
    routes = Counter(str(item.get("route_id")) for item in observations)
    spatial_cells = Counter(str(item.get("spatial_cell")) for item in observations)
    methods = Counter(str(item.get("eta_method")) for item in observations)
    return {
        "outcome_count": total,
        "route_count": len(routes),
        "spatial_cell_count": len(spatial_cells),
        "eta_method_count": len(methods),
        "maximum_single_route_share": round(_share(routes, total), 4),
        "maximum_single_spatial_cell_share": round(
            _share(spatial_cells, total), 4
        ),
        "maximum_single_eta_method_share": round(_share(methods, total), 4),
        "eta_method_shares": {
            name: round(count / total, 4)
            for name, count in sorted(methods.items())
        }
        if total
        else {},
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
    observations_by_band = {
        band: [item for _, _, item in observations if item.get("candidate_band") == band]
        for band in _BANDS
    }
    diversity_by_band = {
        band: _band_diversity(observations_by_band[band]) for band in _BANDS
    }
    daily_stability = _daily_stability(observations)
    all_dayparts = {"morning_peak", "interpeak", "evening_peak", "night"}
    gates = {
        "fourteen_independent_days": len(dates) >= _MINIMUM_INDEPENDENT_DAYS,
        "all_dayparts": all(dayparts[name] > 0 for name in all_dayparts),
        "minimum_50_outcomes_per_band": all(bands[band] >= 50 for band in _BANDS),
        "maximum_single_route_share_20_percent": maximum_route_share <= 0.2,
        "minimum_10_routes_per_band": all(
            int(diversity_by_band[band]["route_count"]) >= _MINIMUM_ROUTES_PER_BAND
            for band in _BANDS
        ),
        "maximum_single_route_share_20_percent_per_band": all(
            float(diversity_by_band[band]["maximum_single_route_share"])
            <= _MAXIMUM_ROUTE_SHARE
            for band in _BANDS
        ),
        "minimum_3_spatial_cells_per_band": all(
            int(diversity_by_band[band]["spatial_cell_count"])
            >= _MINIMUM_SPATIAL_CELLS_PER_BAND
            for band in _BANDS
        ),
        "maximum_single_spatial_cell_share_50_percent_per_band": all(
            float(diversity_by_band[band]["maximum_single_spatial_cell_share"])
            <= _MAXIMUM_SPATIAL_CELL_SHARE
            for band in _BANDS
        ),
        "maximum_single_eta_method_share_95_percent_per_band": all(
            float(diversity_by_band[band]["maximum_single_eta_method_share"])
            <= _MAXIMUM_ETA_METHOD_SHARE
            for band in _BANDS
        ),
        "minimum_70_percent_monotonic_days_mae": (
            float(daily_stability["monotonic_mae_day_rate"])
            >= _MINIMUM_MONOTONIC_DAY_RATE
        ),
        "minimum_70_percent_monotonic_days_p90": (
            float(daily_stability["monotonic_p90_day_rate"])
            >= _MINIMUM_MONOTONIC_DAY_RATE
        ),
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
            "candidate_version": _CANDIDATE_VERSION,
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
            "diversity_by_band": diversity_by_band,
            "daily_stability": daily_stability,
        },
        "gates": gates,
        "calibration_candidate": None,
    }
    if not all(gates.values()):
        return result

    heldout_dates = set(dates[-_HOLDOUT_DAY_COUNT:])
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
    monotonic_heldout_p90 = (
        heldout_metrics["high"]["error_p90_seconds"]
        <= heldout_metrics["medium"]["error_p90_seconds"]
        <= heldout_metrics["low"]["error_p90_seconds"]
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
        "heldout_monotonic_p90": monotonic_heldout_p90,
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
