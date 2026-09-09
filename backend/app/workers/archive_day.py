from __future__ import annotations

import argparse
import asyncio
import json
import logging
from datetime import UTC, date, datetime, timedelta

from app.core.config import settings
from app.infrastructure.archive_factory import build_archive_writer
from app.infrastructure.postgres import (
    PostgresArchiveManifestCatalog,
    PostgresHistoricalPositionSource,
    create_postgres_pool,
)
from app.modules.mobility.adapters.rio import RIO_SOURCE
from app.modules.mobility.archive.service import ArchiveDayService

logger = logging.getLogger("archive_day")


def _parse_day(raw: str | None) -> date:
    if raw:
        return date.fromisoformat(raw)
    return (datetime.now(UTC) - timedelta(days=1)).date()


async def run(*, day: date) -> None:
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(message)s")
    # Full-day archival intentionally streams millions of rows. Keep the short
    # default timeout for request/ingestion paths, but do not time out this
    # bounded maintenance transaction between cursor fetches.
    pool = await create_postgres_pool(settings.database_url, command_timeout=None)
    try:
        service = ArchiveDayService(
            source=RIO_SOURCE,
            historical_source=PostgresHistoricalPositionSource(pool),
            writer=build_archive_writer(settings),
            catalog=PostgresArchiveManifestCatalog(pool),
            batch_size=settings.archive_batch_size,
        )
        report = await service.run_day(day=day)
        logger.info("archive_report %s", json.dumps(report.model_dump(mode="json")))
    finally:
        await pool.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Archive one UTC transit day to Parquet")
    parser.add_argument("--day", help="UTC day in YYYY-MM-DD; defaults to yesterday")
    args = parser.parse_args()
    asyncio.run(run(day=_parse_day(args.day)))


if __name__ == "__main__":
    main()
