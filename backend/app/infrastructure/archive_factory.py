from __future__ import annotations

from pathlib import Path

from app.infrastructure.parquet import (
    LocalParquetArchiveWriter,
    S3CompatibleParquetArchiveWriter,
    create_s3_compatible_client,
)


def build_archive_writer(settings):
    settings.validate_archive_storage()
    kind = settings.archive_storage_kind.lower()
    spool_root = Path(settings.archive_local_root)
    if kind in {"local", "filesystem"}:
        return LocalParquetArchiveWriter(spool_root)
    if kind in {"s3", "oci-s3", "r2"}:
        client = create_s3_compatible_client(
            endpoint_url=settings.archive_s3_endpoint,
            region_name=settings.archive_s3_region,
            access_key_id=settings.archive_s3_access_key_id,
            secret_access_key=settings.archive_s3_secret_access_key,
        )
        return S3CompatibleParquetArchiveWriter(
            client=client,
            bucket=settings.archive_s3_bucket,
            prefix=settings.archive_s3_prefix,
            spool_root=spool_root,
        )
    raise RuntimeError(f"unsupported archive storage kind: {settings.archive_storage_kind}")
