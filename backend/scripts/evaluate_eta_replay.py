from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from math import floor
from typing import Any

from app.core.config import settings
from app.infrastructure.gtfs_postgres import PostgresGtfsCatalog
from app.infrastructure.postgres import create_postgres_pool
from app.modules.mobility.confidence import (
    CANDIDATE_CONFIDENCE_VERSION,
    CandidateConfidenceBand,
    assess_candidate_confidence,
)
from app.modules.mobility.confidence_contract import (
    SHADOW_CONFIDENCE_CONTRACT_VERSION,
    build_shadow_confidence_contract,
)
from app.modules.mobility.models import VehiclePosition

EVALUATION_SCHEMA_VERSION = 2
CALIBRATION_OBSERVATION_SCHEMA_VERSION = 1


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate ETA V0 against later GPS arrivals")
    parser.add_argument("--anchor-age-minutes", type=int, default=20)
    parser.add_argument("--anchor-window-seconds", type=int, default=60)
    parser.add_argument("--outcome-horizon-minutes", type=int, default=20)
    parser.add_argument("--stop-radius-m", type=float, default=75)
    parser.add_argument("--max-samples", type=int, default=50)
    parser.add_argument("--min-outcomes", type=int, default=20)
    parser.add_argument(
        "--anchor-at",
        type=datetime.fromisoformat,
        help="Fixed ISO-8601 anchor end for reproducible comparisons.",
    )
    parser.add_argument("--without-historical-profiles", action="store_true")
    args = parser.parse_args()
    if args.anchor_age_minutes < args.outcome_horizon_minutes:
        parser.error("anchor age must cover the complete outcome horizon")
    if args.anchor_window_seconds not in range(10, 301):
        parser.error("anchor window must be between 10 and 300 seconds")
    if args.outcome_horizon_minutes not in range(1, 121):
        parser.error("outcome horizon must be between 1 and 120 minutes")
    if not 10 <= args.stop_radius_m <= 200:
        parser.error("stop radius must be between 10 and 200 metres")
    if args.max_samples not in range(1, 501):
        parser.error("max samples must be between 1 and 500")
    if args.min_outcomes not in range(1, args.max_samples + 1):
        parser.error("min outcomes must be between 1 and max samples")
    return args


def _percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * quantile
    lower = floor(index)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = index - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _error_diagnostics(
    signed_errors: list[float], *, interval_hits: int = 0
) -> dict[str, int | float | None]:
    absolute_errors = [abs(value) for value in signed_errors]
    count = len(absolute_errors)
    mae = sum(absolute_errors) / count if count else None
    bias = sum(signed_errors) / count if count else None
    over_300_count = sum(value > 300 for value in absolute_errors)
    return {
        "outcome_count": count,
        "mae_seconds": round(mae, 3) if mae is not None else None,
        "bias_seconds": round(bias, 3) if bias is not None else None,
        "error_p50_seconds": (
            round(value, 3)
            if (value := _percentile(absolute_errors, 0.5)) is not None
            else None
        ),
        "error_p90_seconds": (
            round(value, 3)
            if (value := _percentile(absolute_errors, 0.9)) is not None
            else None
        ),
        "interval_coverage": round(interval_hits / count, 4) if count else None,
        "error_over_300_seconds_count": over_300_count,
        "error_over_300_seconds_rate": (
            round(over_300_count / count, 4) if count else None
        ),
    }


def _grouped_error_diagnostics(
    groups: dict[str, list[float]],
    interval_hits: Counter[str],
) -> dict[str, object]:
    return {
        name: _error_diagnostics(values, interval_hits=interval_hits[name])
        for name, values in sorted(groups.items())
    }


def _distance_diagnostics(values: list[float]) -> dict[str, int | float | None]:
    return {
        "count": len(values),
        "p50_m": (
            round(value, 3)
            if (value := _percentile(values, 0.5)) is not None
            else None
        ),
        "p90_m": (
            round(value, 3)
            if (value := _percentile(values, 0.9)) is not None
            else None
        ),
        "max_m": round(max(values), 3) if values else None,
    }


def _speed_diagnostics(values: list[float]) -> dict[str, int | float | None]:
    stopped_count = sum(value < 0.5 for value in values)
    return {
        "count": len(values),
        "p50_mps": (
            round(value, 3)
            if (value := _percentile(values, 0.5)) is not None
            else None
        ),
        "p90_mps": (
            round(value, 3)
            if (value := _percentile(values, 0.9)) is not None
            else None
        ),
        "max_mps": round(max(values), 3) if values else None,
        "stopped_below_0_5_mps_count": stopped_count,
        "stopped_below_0_5_mps_rate": (
            round(stopped_count / len(values), 4) if values else None
        ),
    }


def _candidate_confidence_report(
    errors_by_band: dict[str, list[float]],
    interval_hits_by_band: Counter[str],
    scores: list[int],
    component_totals: Counter[str],
    reason_counts: Counter[str],
) -> dict[str, object]:
    bands: dict[str, object] = {}
    maes: dict[str, float] = {}
    for band in CandidateConfidenceBand:
        errors = errors_by_band.get(band.value, [])
        count = len(errors)
        mae = sum(errors) / count if count else None
        if mae is not None:
            maes[band.value] = mae
        p90 = _percentile(errors, 0.9)
        bands[band.value] = {
            "outcome_count": count,
            "mae_seconds": round(mae, 3) if mae is not None else None,
            "error_p90_seconds": round(p90, 3) if p90 is not None else None,
            "interval_coverage": (
                round(interval_hits_by_band[band.value] / count, 4)
                if count
                else None
            ),
        }
    monotonic_mae = None
    if all(band.value in maes for band in CandidateConfidenceBand):
        monotonic_mae = (
            maes[CandidateConfidenceBand.HIGH.value]
            <= maes[CandidateConfidenceBand.MEDIUM.value]
            <= maes[CandidateConfidenceBand.LOW.value]
        )
    return {
        "candidate_version": CANDIDATE_CONFIDENCE_VERSION,
        "calibration_status": "uncalibrated",
        "mean_score": round(sum(scores) / len(scores), 3) if scores else None,
        "score_p10": (
            round(value, 3) if (value := _percentile(scores, 0.1)) is not None else None
        ),
        "score_p50": (
            round(value, 3) if (value := _percentile(scores, 0.5)) is not None else None
        ),
        "score_p90": (
            round(value, 3) if (value := _percentile(scores, 0.9)) is not None else None
        ),
        "mean_components": {
            name: round(total / len(scores), 3)
            for name, total in sorted(component_totals.items())
        }
        if scores
        else {},
        "reasons": dict(sorted(reason_counts.items())),
        "monotonic_mae": monotonic_mae,
        "bands": bands,
    }


async def _anchors(
    conn: Any, args: argparse.Namespace
) -> tuple[list[VehiclePosition], datetime]:
    anchor_end = getattr(args, "anchor_at", None)
    if anchor_end is None:
        anchor_end = datetime.now(UTC) - timedelta(minutes=args.anchor_age_minutes)
    elif anchor_end.tzinfo is None:
        anchor_end = anchor_end.replace(tzinfo=UTC)
    rows = await conn.fetch(
        """
        WITH latest AS (
            SELECT DISTINCT ON (position.agency_id,position.vehicle_id)
                position.agency_id, position.vehicle_id, position.route_id,
                position.trip_id, position.shape_id,
                position.latitude, position.longitude,
                position.speed_mps, position.bearing_deg, position.observed_at,
                position.received_at, position.source,
                position.quality_status, position.quality_score
            FROM transit.vehicle_positions position
            WHERE position.observed_at <= $1::timestamptz
              AND position.observed_at >= $1::timestamptz
                  - ($2::double precision * interval '1 second')
              AND position.shape_id IS NOT NULL
              AND position.quality_status <> 'invalid'
            ORDER BY
                position.agency_id,
                position.vehicle_id,
                position.observed_at DESC
        )
        SELECT *
        FROM latest
        ORDER BY md5(
            latest.agency_id || ':' || latest.vehicle_id || ':' || $1::text
        )
        LIMIT $3
        """,
        anchor_end,
        float(args.anchor_window_seconds),
        args.max_samples,
    )
    return [VehiclePosition.model_validate(dict(row)) for row in rows], anchor_end


async def _actual_arrival(
    conn: Any,
    *,
    position: VehiclePosition,
    evaluated_at: datetime,
    stop_latitude: float,
    stop_longitude: float,
    horizon_minutes: int,
    radius_m: float,
):
    return await conn.fetchval(
        """
        SELECT observed_at
        FROM transit.vehicle_positions
        WHERE agency_id = $1
          AND vehicle_id = $2
          AND route_id = $3
          AND observed_at >= $4
          AND observed_at <= $4::timestamptz
              + ($5::double precision * interval '1 minute')
          AND quality_status <> 'invalid'
          AND ST_DWithin(
              location,
              ST_SetSRID(ST_MakePoint($7,$6),4326)::geography,
              $8
          )
        ORDER BY observed_at
        LIMIT 1
        """,
        position.agency_id,
        position.vehicle_id,
        position.route_id,
        evaluated_at,
        float(horizon_minutes),
        stop_latitude,
        stop_longitude,
        radius_m,
    )


async def _run(
    args: argparse.Namespace,
    *,
    database_url: str | None = None,
) -> dict[str, object]:
    pool = await create_postgres_pool(database_url or settings.database_url, command_timeout=None)
    reasons: Counter[str] = Counter()
    methods: Counter[str] = Counter()
    match_methods: Counter[str] = Counter()
    errors: list[float] = []
    signed_errors: list[float] = []
    interval_hits = 0
    confidence_errors: dict[str, list[float]] = defaultdict(list)
    confidence_interval_hits: Counter[str] = Counter()
    confidence_scores: list[int] = []
    confidence_component_totals: Counter[str] = Counter()
    confidence_reason_counts: Counter[str] = Counter()
    errors_by_method: dict[str, list[float]] = defaultdict(list)
    errors_by_match_method: dict[str, list[float]] = defaultdict(list)
    errors_by_route: dict[str, list[float]] = defaultdict(list)
    interval_hits_by_method: Counter[str] = Counter()
    interval_hits_by_match_method: Counter[str] = Counter()
    interval_hits_by_route: Counter[str] = Counter()
    excluded_projection_distances: dict[str, list[float]] = defaultdict(list)
    excluded_speeds: dict[str, list[float]] = defaultdict(list)
    excluded_routes: Counter[tuple[str, str]] = Counter()
    calibration_observations: list[dict[str, object]] = []
    try:
        async with pool.acquire() as conn, conn.transaction(readonly=True):
            anchors, anchor_end = await _anchors(conn, args)
            catalog = PostgresGtfsCatalog(
                pool,
                historical_profiles_enabled=not getattr(
                    args, "without_historical_profiles", False
                ),
            )
            for position in anchors:
                match = await catalog.match_vehicle_to_upcoming_stops(
                    position=position,
                    limit=1,
                    max_projection_distance_m=250,
                    evaluated_at=anchor_end,
                )
                if not match.available:
                    reason = str(match.unavailable_reason or "match_unavailable")
                    reasons[reason] += 1
                    excluded_routes[(reason, position.route_id)] += 1
                    if match.projection_distance_m is not None:
                        excluded_projection_distances[reason].append(
                            match.projection_distance_m
                        )
                    if position.speed_mps is not None:
                        excluded_speeds[reason].append(position.speed_mps)
                    continue
                if match.eta_evidence is None:
                    reasons[str(match.eta_unavailable_reason or "eta_unavailable")] += 1
                    continue
                stop = match.upcoming_stops[0]
                if stop.estimated_arrival_at is None:
                    reasons[str(stop.eta_unavailable_reason or "stop_eta_unavailable")] += 1
                    continue
                actual_arrival = await _actual_arrival(
                    conn,
                    position=position,
                    evaluated_at=anchor_end,
                    stop_latitude=stop.latitude,
                    stop_longitude=stop.longitude,
                    horizon_minutes=args.outcome_horizon_minutes,
                    radius_m=args.stop_radius_m,
                )
                if actual_arrival is None:
                    reasons["arrival_not_observed"] += 1
                    continue
                method = match.eta_evidence.method.value
                match_method = str(match.match_method or "unknown")
                methods[method] += 1
                match_methods[match_method] += 1
                actual_eta_seconds = (actual_arrival - anchor_end).total_seconds()
                predicted_eta_seconds = float(stop.eta_seconds or 0)
                signed_error = predicted_eta_seconds - actual_eta_seconds
                signed_errors.append(signed_error)
                absolute_error = abs(signed_error)
                errors.append(absolute_error)
                errors_by_method[method].append(signed_error)
                errors_by_match_method[match_method].append(signed_error)
                errors_by_route[position.route_id].append(signed_error)
                confidence = assess_candidate_confidence(
                    evidence=match.eta_evidence,
                    position_age_seconds=match.position_age_seconds or 0,
                    projection_distance_m=match.projection_distance_m or 0,
                    match_method=match.match_method,
                )
                shadow_confidence = build_shadow_confidence_contract(
                    candidate=confidence,
                    calibration_status="uncalibrated",
                    estimated_eta_seconds=stop.eta_seconds,
                    lower_eta_seconds=stop.eta_lower_seconds,
                    upper_eta_seconds=stop.eta_upper_seconds,
                )
                confidence_errors[confidence.band.value].append(absolute_error)
                confidence_scores.append(confidence.score)
                confidence_component_totals.update(confidence.components)
                confidence_reason_counts.update(confidence.reasons)
                interval_hit = (
                    stop.eta_lower_seconds is not None
                    and stop.eta_upper_seconds is not None
                    and stop.eta_lower_seconds
                    <= actual_eta_seconds
                    <= stop.eta_upper_seconds
                )
                calibration_observations.append(
                    {
                        "score": confidence.score,
                        "candidate_band": confidence.band.value,
                        "signed_error_seconds": round(signed_error, 3),
                        "absolute_error_seconds": round(absolute_error, 3),
                        "predicted_eta_seconds": round(predicted_eta_seconds, 3),
                        "actual_eta_seconds": round(actual_eta_seconds, 3),
                        "eta_lower_seconds": stop.eta_lower_seconds,
                        "eta_upper_seconds": stop.eta_upper_seconds,
                        "interval_hit": interval_hit,
                        "eta_method": method,
                        "match_method": match_method,
                        "route_id": position.route_id,
                        "position_age_seconds": round(
                            float(match.position_age_seconds or 0), 3
                        ),
                        "projection_distance_m": round(
                            float(match.projection_distance_m or 0), 3
                        ),
                        "shape_distance_ahead_m": round(
                            float(stop.shape_distance_ahead), 3
                        ),
                        "evidence_sample_count": match.eta_evidence.sample_count,
                        "evidence_window_seconds": match.eta_evidence.window_seconds,
                        "confidence_components": confidence.components,
                        "confidence_reasons": list(confidence.reasons),
                        "shadow_confidence": shadow_confidence.model_dump(mode="json"),
                    }
                )
                if interval_hit:
                    interval_hits += 1
                    confidence_interval_hits[confidence.band.value] += 1
                    interval_hits_by_method[method] += 1
                    interval_hits_by_match_method[match_method] += 1
                    interval_hits_by_route[position.route_id] += 1
    finally:
        await pool.close()

    outcome_count = len(errors)
    return {
        "evaluation_schema_version": EVALUATION_SCHEMA_VERSION,
        "calibration_observation_schema_version": (
            CALIBRATION_OBSERVATION_SCHEMA_VERSION
        ),
        "shadow_confidence_contract_version": SHADOW_CONFIDENCE_CONTRACT_VERSION,
        "status": (
            "sufficient_data" if outcome_count >= args.min_outcomes else "insufficient_data"
        ),
        "anchor_count": len(anchors),
        "outcome_count": outcome_count,
        "minimum_outcomes": args.min_outcomes,
        "mae_seconds": round(sum(errors) / outcome_count, 3) if errors else None,
        "bias_seconds": (
            round(sum(signed_errors) / outcome_count, 3) if signed_errors else None
        ),
        "error_p50_seconds": (
            round(value, 3) if (value := _percentile(errors, 0.5)) is not None else None
        ),
        "error_p90_seconds": (
            round(value, 3) if (value := _percentile(errors, 0.9)) is not None else None
        ),
        "methods": dict(sorted(methods.items())),
        "match_methods": dict(sorted(match_methods.items())),
        "interval_coverage": (
            round(interval_hits / outcome_count, 4) if outcome_count else None
        ),
        "excluded_reasons": dict(sorted(reasons.items())),
        "diagnostics": {
            "overall": _error_diagnostics(
                signed_errors,
                interval_hits=interval_hits,
            ),
            "by_eta_method": _grouped_error_diagnostics(
                errors_by_method,
                interval_hits_by_method,
            ),
            "by_match_method": _grouped_error_diagnostics(
                errors_by_match_method,
                interval_hits_by_match_method,
            ),
            "top_routes": [
                {
                    "route_id": route_id,
                    **_error_diagnostics(
                        route_errors,
                        interval_hits=interval_hits_by_route[route_id],
                    ),
                }
                for route_id, route_errors in sorted(
                    errors_by_route.items(),
                    key=lambda item: (-len(item[1]), item[0]),
                )[:10]
            ],
            "excluded_projection_distance_m": {
                reason: _distance_diagnostics(values)
                for reason, values in sorted(excluded_projection_distances.items())
            },
            "excluded_speed_mps": {
                reason: _speed_diagnostics(values)
                for reason, values in sorted(excluded_speeds.items())
            },
            "top_excluded_routes": [
                {"reason": reason, "route_id": route_id, "count": count}
                for (reason, route_id), count in sorted(
                    excluded_routes.items(),
                    key=lambda item: (-item[1], item[0]),
                )[:10]
            ],
        },
        "candidate_confidence": _candidate_confidence_report(
            confidence_errors,
            confidence_interval_hits,
            confidence_scores,
            confidence_component_totals,
            confidence_reason_counts,
        ),
        "calibration_observations": calibration_observations,
        "parameters": {
            "anchor_age_minutes": args.anchor_age_minutes,
            "anchor_window_seconds": args.anchor_window_seconds,
            "outcome_horizon_minutes": args.outcome_horizon_minutes,
            "stop_radius_m": args.stop_radius_m,
            "max_samples": args.max_samples,
            "anchor_at": (
                args.anchor_at.isoformat() if getattr(args, "anchor_at", None) else None
            ),
            "effective_anchor_at": anchor_end.isoformat(),
            "historical_profiles_enabled": not getattr(
                args, "without_historical_profiles", False
            ),
            "sampling_method": "deterministic_vehicle_hash_v1",
        },
    }


def main() -> None:
    args = _parse_args()
    report = asyncio.run(_run(args))
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
