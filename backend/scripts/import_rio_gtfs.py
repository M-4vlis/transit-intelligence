from __future__ import annotations

import argparse
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


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import and atomically activate Rio GTFS")
    parser.add_argument(
        "--no-activate",
        action="store_true",
        help="Import the snapshot as ready without changing the active snapshot",
    )
    parser.add_argument(
        "--activate-snapshot",
        help="Activate an already imported snapshot by SHA-256 (rollback)",
    )
    return parser.parse_args()


async def _download_and_import(*, activate: bool) -> dict[str, object]:
    timeout = httpx.Timeout(
        settings.source_timeout_seconds, connect=settings.source_timeout_seconds
    )
    with tempfile.TemporaryDirectory(prefix="transit-gtfs-import-") as temporary_directory:
        download_path = Path(temporary_directory) / "rio-gtfs.zip"
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            downloader = ResilientBinaryDownloader(
                client,
                policy=RetryPolicy(max_attempts=4),
                max_response_bytes=settings.gtfs_max_compressed_bytes,
            )
            artifact = await downloader.download(
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
            result = await PostgresGtfsImporter(pool).import_snapshot(
                artifact.path,
                manifest,
                activate=activate,
            )
        finally:
            await pool.close()
    return result.model_dump(mode="json")


async def _activate_existing(snapshot_id: str) -> dict[str, object]:
    if len(snapshot_id) != 64 or any(
        character not in "0123456789abcdef" for character in snapshot_id
    ):
        raise ValueError("snapshot id must be a lowercase SHA-256")
    pool = await create_postgres_pool(settings.database_url)
    try:
        await PostgresGtfsImporter(pool).activate_snapshot(snapshot_id)
    finally:
        await pool.close()
    return {"snapshot_id": snapshot_id, "active": True, "rollback": True}


async def _run(args: argparse.Namespace) -> None:
    if args.activate_snapshot:
        payload = await _activate_existing(args.activate_snapshot)
    else:
        payload = await _download_and_import(activate=not args.no_activate)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))


def main() -> None:
    asyncio.run(_run(_parse_args()))


if __name__ == "__main__":
    main()
