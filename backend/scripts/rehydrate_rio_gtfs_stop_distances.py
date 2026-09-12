from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

import httpx

from app.core.config import settings
from app.infrastructure.postgres import create_postgres_pool
from app.modules.mobility.gtfs.importer import PostgresGtfsImporter
from app.modules.mobility.gtfs.validator import validate_gtfs_snapshot
from app.modules.mobility.sources.http import ResilientBinaryDownloader, RetryPolicy


async def _run() -> None:
    timeout = httpx.Timeout(
        settings.source_timeout_seconds,
        connect=settings.source_timeout_seconds,
    )
    with tempfile.TemporaryDirectory(prefix="transit-gtfs-rehydrate-") as temporary_directory:
        download_path = Path(temporary_directory) / "rio-gtfs.zip"
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            artifact = await ResilientBinaryDownloader(
                client,
                policy=RetryPolicy(max_attempts=4),
                max_response_bytes=settings.gtfs_max_compressed_bytes,
            ).download(
                settings.rio_gtfs_url,
                download_path,
                allowed_hosts=settings.gtfs_allowed_source_hosts,
            )
        manifest = validate_gtfs_snapshot(
            artifact.path,
            source_url=settings.rio_gtfs_url,
            expected_sha256=artifact.sha256,
            max_compressed_bytes=settings.gtfs_max_compressed_bytes,
            max_uncompressed_bytes=settings.gtfs_max_uncompressed_bytes,
            max_members=settings.gtfs_max_members,
        )
        pool = await create_postgres_pool(settings.database_url, command_timeout=None)
        try:
            result = await PostgresGtfsImporter(pool).rehydrate_stop_distances(
                artifact.path,
                manifest,
            )
        finally:
            await pool.close()
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, indent=2))


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
