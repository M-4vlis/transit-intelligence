from __future__ import annotations

import argparse
import asyncio
import json
import tempfile
from datetime import date
from hashlib import sha256
from pathlib import Path

from app.core.config import settings
from app.infrastructure.parquet import create_s3_compatible_client
from app.infrastructure.postgres import PostgresArchiveManifestCatalog, create_postgres_pool
from app.modules.mobility.adapters.rio import RIO_SOURCE


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Restore and verify one remote Parquet archive")
    parser.add_argument("--day", required=True, type=date.fromisoformat)
    parser.add_argument("--keep", action="store_true")
    return parser.parse_args()


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _object_key(object_uri: str, *, bucket: str) -> str:
    prefix = f"s3://{bucket}/"
    if not object_uri.startswith(prefix):
        raise ValueError("archive manifest object URI does not belong to configured bucket")
    key = object_uri[len(prefix) :]
    if not key or key.startswith("/") or ".." in key.split("/"):
        raise ValueError("unsafe archive object key")
    return key


async def run(args: argparse.Namespace) -> dict[str, object]:
    settings.validate_archive_storage()
    if settings.archive_storage_kind.lower() not in {"s3", "oci-s3", "r2"}:
        raise RuntimeError("restore check requires external S3-compatible archive storage")

    try:
        import pyarrow.parquet as pq
    except ModuleNotFoundError as exc:
        raise RuntimeError("archive restore check requires project archive dependencies") from exc

    pool = await create_postgres_pool(settings.database_url)
    try:
        catalog = PostgresArchiveManifestCatalog(pool)
        artifact = await catalog.get_verified(source=RIO_SOURCE, day=args.day)
    finally:
        await pool.close()
    if artifact is None:
        raise RuntimeError(f"no verified archive manifest for {RIO_SOURCE} on {args.day}")

    client = create_s3_compatible_client(
        endpoint_url=settings.archive_s3_endpoint,
        region_name=settings.archive_s3_region,
        access_key_id=settings.archive_s3_access_key_id,
        secret_access_key=settings.archive_s3_secret_access_key,
    )
    key = _object_key(artifact.object_uri, bucket=settings.archive_s3_bucket)

    temp_dir = Path(tempfile.mkdtemp(prefix="transit-restore-"))
    restored = temp_dir / f"{args.day.isoformat()}.parquet"
    try:
        await asyncio.to_thread(
            client.download_file,
            settings.archive_s3_bucket,
            key,
            str(restored),
        )
        restored_size = restored.stat().st_size
        restored_hash = _sha256_file(restored)
        parquet = pq.ParquetFile(restored)
        restored_rows = int(parquet.metadata.num_rows)
        passed = (
            restored_size == artifact.byte_size
            and restored_hash == artifact.sha256
            and restored_rows == artifact.row_count
        )
        return {
            "passed": passed,
            "source": artifact.source,
            "archive_day": artifact.archive_day.isoformat(),
            "object_uri": artifact.object_uri,
            "expected": {
                "row_count": artifact.row_count,
                "byte_size": artifact.byte_size,
                "sha256": artifact.sha256,
            },
            "restored": {
                "row_count": restored_rows,
                "byte_size": restored_size,
                "sha256": restored_hash,
                "local_path": str(restored) if args.keep else None,
            },
        }
    finally:
        if not args.keep:
            restored.unlink(missing_ok=True)
            try:
                temp_dir.rmdir()
            except OSError:
                pass


def main() -> int:
    payload = asyncio.run(run(parse_args()))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
