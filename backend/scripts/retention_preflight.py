from __future__ import annotations

import asyncio
import json
from dataclasses import asdict

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


async def run() -> dict[str, object]:
    settings.validate_archive_storage()
    if not settings.retention_is_safe:
        raise RuntimeError("retention preflight requires durable external archive storage")

    writer = build_archive_writer(settings)
    pool = await create_postgres_pool(settings.database_url, command_timeout=None)
    try:
        catalog = PostgresArchiveManifestCatalog(pool)
        guard = RemoteVerifiedArchiveGuard(catalog=catalog, writer=writer)
        service = SafeHotRetentionService(
            source=RIO_SOURCE,
            hot_repository=PostgresHotPartitionRepository(pool),
            archive_catalog=guard,
            retention_days=settings.hot_retention_days,
        )
        report = await service.run_once(dry_run=True)
    finally:
        await pool.close()

    payload = asdict(report)
    payload["mode"] = "dry-run"
    payload["source"] = RIO_SOURCE
    payload["destructive_retention_enabled"] = settings.destructive_retention_enabled
    return payload


def main() -> int:
    payload = asyncio.run(run())
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
