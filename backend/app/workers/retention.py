from __future__ import annotations

import asyncio
from dataclasses import asdict
import json
import logging

from app.core.config import settings
from app.infrastructure.archive_factory import build_archive_writer
from app.infrastructure.postgres import (
    PostgresArchiveManifestCatalog,
    PostgresHotPartitionRepository,
    create_postgres_pool,
)
from app.modules.mobility.adapters.rio import RIO_SOURCE
from app.modules.mobility.retention.guard import RemoteVerifiedArchiveGuard
from app.modules.mobility.retention.service import SafeHotRetentionService

logger = logging.getLogger("hot_retention")


async def run() -> None:
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(message)s")
    if not settings.destructive_retention_enabled:
        logger.warning("destructive retention disabled; no partitions will be dropped")
        return

    settings.validate_archive_storage()
    settings.validate_destructive_retention()
    writer = build_archive_writer(settings)
    pool = await create_postgres_pool(settings.database_url)
    try:
        catalog = PostgresArchiveManifestCatalog(pool)
        guard = RemoteVerifiedArchiveGuard(catalog=catalog, writer=writer)
        service = SafeHotRetentionService(
            source=RIO_SOURCE,
            hot_repository=PostgresHotPartitionRepository(pool),
            archive_catalog=guard,
            retention_days=settings.hot_retention_days,
        )
        report = await service.run_once()
        logger.info("retention_report %s", json.dumps(asdict(report), default=str))
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(run())
