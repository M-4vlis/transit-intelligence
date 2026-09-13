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
    CandidateConfidenceBand,
    assess_candidate_confidence,
)
from app.modules.mobility.models import VehiclePosition


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
        SELECT DISTINCT ON (position.agency_id,position.vehicle_id)
            position.agency_id, position.vehicle_id, position.route_id,
            position.trip_id, position.shape_id, position.latitude, position.longitude,
            position.speed_mps, position.bearing_deg, position.observed_at,
            position.received_at, position.source,
            position.quality_status, position.quality_score
        FROM transit.vehicle_positions position
        WHERE position.observed_at <= $1::timestamptz
          AND position.observed_at >= $1::timestamptz
              - ($2::double precision * interval '1 second')
          AND position.shape_id IS NOT NULL
          AND position.quality_status <> 'invalid'
        ORDER BY position.agency_id, position.vehicle_id, position.observed_at DESC
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
        position.observed_at,
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
                    reasons[str(match.unavailable_reason or "match_unavailable")] += 1
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
                    stop_latitude=stop.latitude,
                    stop_longitude=stop.longitude,
                    horizon_minutes=args.outcome_horizon_minutes,
                    radius_m=args.stop_radius_m,
                )
                if actual_arrival is None:
                    reasons["arrival_not_observed"] += 1
                    continue
                methods[match.eta_evidence.method.value] += 1
                match_methods[str(match.match_method or "unknown")] += 1
                signed_error = (stop.estimated_arrival_at - actual_arrival).total_seconds()
                signed_errors.append(signed_error)
                absolute_error = abs(signed_error)
                errors.append(absolute_error)
                confidence = assess_candidate_confidence(
                    evidence=match.eta_evidence,
                    position_age_seconds=match.position_age_seconds or 0,
                    projection_distance_m=match.projection_distance_m or 0,
                    match_method=match.match_method,
                )
                confidence_errors[confidence.band.value].append(absolute_error)
                confidence_scores.append(confidence.score)
                confidence_component_totals.update(confidence.components)
                confidence_reason_counts.update(confidence.reasons)
                actual_eta_seconds = (actual_arrival - position.observed_at).total_seconds()
                interval_hit = (
                    stop.eta_lower_seconds is not None
                    and stop.eta_upper_seconds is not None
                    and stop.eta_lower_seconds
                    <= actual_eta_seconds
                    <= stop.eta_upper_seconds
                )
                if interval_hit:
                    interval_hits += 1
                    confidence_interval_hits[confidence.band.value] += 1
    finally:
        await pool.close()

    outcome_count = len(errors)
    return {
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
        "candidate_confidence": _candidate_confidence_report(
            confidence_errors,
            confidence_interval_hits,
            confidence_scores,
            confidence_component_totals,
            confidence_reason_counts,
        ),
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
        },
    }


def main() -> None:
    args = _parse_args()
    report = asyncio.run(_run(args))
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
