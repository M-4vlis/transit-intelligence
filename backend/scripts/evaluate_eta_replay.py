from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from math import floor
from typing import Any

from app.core.config import settings
from app.infrastructure.gtfs_postgres import PostgresGtfsCatalog
from app.infrastructure.postgres import create_postgres_pool
from app.modules.mobility.models import VehiclePosition


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate ETA V0 against later GPS arrivals")
    parser.add_argument("--anchor-age-minutes", type=int, default=20)
    parser.add_argument("--anchor-window-seconds", type=int, default=60)
    parser.add_argument("--outcome-horizon-minutes", type=int, default=20)
    parser.add_argument("--stop-radius-m", type=float, default=75)
    parser.add_argument("--max-samples", type=int, default=50)
    parser.add_argument("--min-outcomes", type=int, default=20)
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


async def _anchors(conn: Any, args: argparse.Namespace) -> list[VehiclePosition]:
    rows = await conn.fetch(
        """
        WITH bounds AS (
            SELECT now() - ($1::double precision * interval '1 minute') AS anchor_end
        )
        SELECT DISTINCT ON (position.agency_id,position.vehicle_id)
            position.agency_id, position.vehicle_id, position.route_id,
            position.trip_id, position.shape_id, position.latitude, position.longitude,
            position.speed_mps, position.bearing_deg, position.observed_at,
            position.received_at, position.source,
            position.quality_status, position.quality_score
        FROM transit.vehicle_positions position
        CROSS JOIN bounds
        WHERE position.observed_at <= bounds.anchor_end
          AND position.observed_at >= bounds.anchor_end
              - ($2::double precision * interval '1 second')
          AND position.shape_id IS NOT NULL
          AND position.quality_status <> 'invalid'
        ORDER BY position.agency_id, position.vehicle_id, position.observed_at DESC
        LIMIT $3
        """,
        float(args.anchor_age_minutes),
        float(args.anchor_window_seconds),
        args.max_samples,
    )
    return [VehiclePosition.model_validate(dict(row)) for row in rows]


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
    try:
        async with pool.acquire() as conn, conn.transaction(readonly=True):
            anchors = await _anchors(conn, args)
            catalog = PostgresGtfsCatalog(pool)
            for position in anchors:
                match = await catalog.match_vehicle_to_upcoming_stops(
                    position=position,
                    limit=1,
                    max_projection_distance_m=250,
                    evaluated_at=position.observed_at,
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
                errors.append(abs(signed_error))
                actual_eta_seconds = (actual_arrival - position.observed_at).total_seconds()
                if (
                    stop.eta_lower_seconds is not None
                    and stop.eta_upper_seconds is not None
                    and stop.eta_lower_seconds
                    <= actual_eta_seconds
                    <= stop.eta_upper_seconds
                ):
                    interval_hits += 1
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
        "parameters": {
            "anchor_age_minutes": args.anchor_age_minutes,
            "anchor_window_seconds": args.anchor_window_seconds,
            "outcome_horizon_minutes": args.outcome_horizon_minutes,
            "stop_radius_m": args.stop_radius_m,
            "max_samples": args.max_samples,
        },
    }


def main() -> None:
    args = _parse_args()
    report = asyncio.run(_run(args))
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
