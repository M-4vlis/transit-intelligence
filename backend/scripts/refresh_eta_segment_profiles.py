from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.config import settings
from app.infrastructure.postgres import create_postgres_pool

PROFILE_WINDOW_MINUTES = 15
MIN_PROFILE_SAMPLES = 3
MIN_SPEED_MPS = 0.8
MAX_SPEED_MPS = 22.22
GRID_DEGREES = 0.0025


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Refresh bounded ETA speed profiles from persisted GPS history."
    )
    parser.add_argument("--lookback-hours", type=float, default=6.0)
    parser.add_argument("--end-delay-minutes", type=int, default=5)
    args = parser.parse_args()
    if not 0.25 <= args.lookback_hours <= 168:
        parser.error("lookback hours must be between 0.25 and 168")
    if args.end_delay_minutes not in range(1, 121):
        parser.error("end delay must be between 1 and 120 minutes")
    return args


def _aligned_window_end(now: datetime, delay_minutes: int) -> datetime:
    safe_now = now.astimezone(UTC) - timedelta(minutes=delay_minutes)
    minute = safe_now.minute - (safe_now.minute % PROFILE_WINDOW_MINUTES)
    return safe_now.replace(minute=minute, second=0, microsecond=0)


async def refresh_profiles(
    conn: Any,
    *,
    start: datetime,
    end: datetime,
) -> int:
    result = await conn.execute(
        """
        INSERT INTO transit.eta_segment_speed_profiles (
            window_start, window_end, route_id, latitude_cell, longitude_cell,
            local_time_band, sample_count, speed_p25_mps, speed_median_mps,
            speed_p75_mps, refreshed_at
        )
        SELECT
            date_bin(
                interval '15 minutes',
                observed_at,
                timestamptz '2000-01-01 00:00:00+00'
            ) AS window_start,
            date_bin(
                interval '15 minutes',
                observed_at,
                timestamptz '2000-01-01 00:00:00+00'
            ) + interval '15 minutes' AS window_end,
            route_id,
            floor((latitude + 90.0) / $3::double precision)::integer,
            floor((longitude + 180.0) / $3::double precision)::integer,
            floor(
                extract(epoch FROM (observed_at AT TIME ZONE 'America/Sao_Paulo')::time)
                / 900
            )::smallint AS local_time_band,
            count(*)::integer AS sample_count,
            percentile_cont(0.25) WITHIN GROUP (ORDER BY speed_mps)::real,
            percentile_cont(0.50) WITHIN GROUP (ORDER BY speed_mps)::real,
            percentile_cont(0.75) WITHIN GROUP (ORDER BY speed_mps)::real,
            now()
        FROM transit.vehicle_positions
        WHERE observed_at >= $1::timestamptz
          AND observed_at < $2::timestamptz
          AND speed_mps BETWEEN $4 AND $5
          AND quality_status <> 'invalid'
          AND route_id <> ''
        GROUP BY window_start, route_id, latitude_cell, longitude_cell, local_time_band
        HAVING count(*) >= $6
        ON CONFLICT (window_start, route_id, latitude_cell, longitude_cell)
        DO UPDATE SET
            window_end = EXCLUDED.window_end,
            local_time_band = EXCLUDED.local_time_band,
            sample_count = EXCLUDED.sample_count,
            speed_p25_mps = EXCLUDED.speed_p25_mps,
            speed_median_mps = EXCLUDED.speed_median_mps,
            speed_p75_mps = EXCLUDED.speed_p75_mps,
            refreshed_at = now()
        """,
        start,
        end,
        GRID_DEGREES,
        MIN_SPEED_MPS,
        MAX_SPEED_MPS,
        MIN_PROFILE_SAMPLES,
    )
    return int(result.rsplit(" ", 1)[-1])


async def _run(args: argparse.Namespace, database_url: str | None = None) -> dict[str, Any]:
    end = _aligned_window_end(datetime.now(UTC), args.end_delay_minutes)
    start = end - timedelta(hours=args.lookback_hours)
    pool = await create_postgres_pool(database_url or settings.database_url, command_timeout=None)
    try:
        async with pool.acquire() as conn, conn.transaction():
            profile_count = await refresh_profiles(conn, start=start, end=end)
    finally:
        await pool.close()
    return {
        "status": "success",
        "start": start.isoformat(),
        "end": end.isoformat(),
        "profile_count": profile_count,
        "lookback_hours": args.lookback_hours,
        "end_delay_minutes": args.end_delay_minutes,
    }


async def main() -> None:
    print(json.dumps(await _run(_arguments()), indent=2, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())
