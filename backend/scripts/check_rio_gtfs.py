from __future__ import annotations

import argparse
import asyncio
import json
import tempfile
from pathlib import Path

import httpx

from app.core.config import settings
from app.modules.mobility.gtfs.validator import validate_gtfs_snapshot
from app.modules.mobility.sources.http import ResilientBinaryDownloader, RetryPolicy


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download and validate the official Rio GTFS")
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Keep a content-addressed ZIP and manifest in this directory",
    )
    return parser.parse_args()


def _persist_snapshot(downloaded: Path, output_dir: Path, manifest_json: str, sha256: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = output_dir / f"{sha256}.zip"
    manifest_path = output_dir / f"{sha256}.json"

    if snapshot_path.exists():
        validate_gtfs_snapshot(
            snapshot_path,
            source_url=settings.rio_gtfs_url,
            expected_sha256=sha256,
            max_compressed_bytes=settings.gtfs_max_compressed_bytes,
            max_uncompressed_bytes=settings.gtfs_max_uncompressed_bytes,
            max_members=settings.gtfs_max_members,
        )
        downloaded.unlink()
    else:
        downloaded.replace(snapshot_path)

    temporary_manifest = manifest_path.with_suffix(".json.part")
    temporary_manifest.write_text(manifest_json + "\n", encoding="utf-8")
    temporary_manifest.replace(manifest_path)


async def _run(output_dir: Path | None) -> None:
    timeout = httpx.Timeout(settings.source_timeout_seconds, connect=settings.source_timeout_seconds)
    with tempfile.TemporaryDirectory(prefix="transit-gtfs-") as temporary_directory:
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
        manifest_json = json.dumps(manifest.model_dump(mode="json"), sort_keys=True)
        if output_dir is not None:
            _persist_snapshot(artifact.path, output_dir, manifest_json, manifest.snapshot_id)
        print(manifest_json)


def main() -> None:
    args = _parse_args()
    asyncio.run(_run(args.output_dir))


if __name__ == "__main__":
    main()
