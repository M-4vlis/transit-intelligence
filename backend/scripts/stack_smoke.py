from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime
import json

from app.core.config import settings
from app.infrastructure.postgres import PostgresOperationalRepository, create_postgres_pool
from app.infrastructure.valkey import create_valkey_client
from app.modules.mobility.adapters.rio import RIO_SOURCE


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-test the deployed data stack")
    parser.add_argument("--max-position-age-seconds", type=float, default=180.0)
    return parser.parse_args()


async def run(args: argparse.Namespace) -> dict[str, object]:
    now = datetime.now(UTC)
    checks: dict[str, bool] = {"database": False, "cache": False, "recent_position": False}
    details: dict[str, object] = {}

    pool = await create_postgres_pool(settings.database_url)
    cache = await create_valkey_client(settings.cache_url)
    try:
        async with pool.acquire() as conn:
            checks["database"] = bool(await conn.fetchval("SELECT true"))
        checks["cache"] = bool(await cache.ping())
        repository = PostgresOperationalRepository(pool)
        latest = await repository.latest_position_observed_at(source=RIO_SOURCE)
        details["latest_position_observed_at"] = latest.isoformat() if latest else None
        if latest is not None:
            age = (now - latest.astimezone(UTC)).total_seconds()
            details["latest_position_age_seconds"] = round(age, 3)
            checks["recent_position"] = age <= args.max_position_age_seconds
    finally:
        await cache.aclose()
        await pool.close()

    return {
        "passed": all(checks.values()),
        "checks": checks,
        "details": details,
        "evaluated_at": now.isoformat(),
    }


def main() -> int:
    payload = asyncio.run(run(parse_args()))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
