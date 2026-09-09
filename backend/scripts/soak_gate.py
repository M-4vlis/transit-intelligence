from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
import json

from app.core.config import settings
from app.infrastructure.postgres import PostgresOperationalRepository, create_postgres_pool
from app.modules.mobility.adapters.rio import RIO_SOURCE
from app.modules.mobility.operations.models import SoakThresholds
from app.modules.mobility.operations.soak import assess_soak


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate realtime ingestion soak health")
    parser.add_argument("--hours", type=float, default=24.0)
    parser.add_argument("--min-cycle-coverage", type=float, default=0.90)
    parser.add_argument("--min-success-ratio", type=float, default=0.98)
    parser.add_argument("--max-rejection-ratio", type=float, default=0.02)
    parser.add_argument("--max-gap-seconds", type=float, default=180.0)
    parser.add_argument("--max-latest-age-seconds", type=float, default=120.0)
    parser.add_argument("--max-contract-fingerprints", type=int, default=1)
    return parser.parse_args()


async def run(args: argparse.Namespace) -> dict[str, object]:
    if args.hours <= 0:
        raise ValueError("--hours must be positive")
    now = datetime.now(UTC)
    window = timedelta(hours=args.hours)
    pool = await create_postgres_pool(settings.database_url)
    try:
        repository = PostgresOperationalRepository(pool)
        runs = await repository.ingestion_runs_since(
            source=RIO_SOURCE,
            since=now - window,
        )
        latest_position = await repository.latest_position_observed_at(source=RIO_SOURCE)
    finally:
        await pool.close()

    assessment = assess_soak(
        runs,
        now=now,
        window=window,
        poll_interval_seconds=settings.rio_poll_interval_seconds,
        thresholds=SoakThresholds(
            min_cycle_coverage=args.min_cycle_coverage,
            min_success_ratio=args.min_success_ratio,
            max_rejection_ratio=args.max_rejection_ratio,
            max_gap_seconds=args.max_gap_seconds,
            max_latest_age_seconds=args.max_latest_age_seconds,
            max_contract_fingerprints=args.max_contract_fingerprints,
        ),
    )
    payload = asdict(assessment)
    payload["source"] = RIO_SOURCE
    payload["evaluated_at"] = now.isoformat()
    payload["latest_position_observed_at"] = (
        latest_position.isoformat() if latest_position is not None else None
    )
    return payload


def main() -> int:
    args = parse_args()
    payload = asyncio.run(run(args))
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 0 if payload["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
