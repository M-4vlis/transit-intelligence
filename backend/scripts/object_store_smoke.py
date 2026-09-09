from __future__ import annotations

from hashlib import sha256
import json
import secrets
from datetime import UTC, datetime

from app.core.config import settings
from app.infrastructure.parquet import create_s3_compatible_client


def main() -> int:
    settings.validate_archive_storage()
    if settings.archive_storage_kind.lower() not in {"s3", "oci-s3", "r2"}:
        raise RuntimeError("object store smoke requires external S3-compatible archive storage")

    client = create_s3_compatible_client(
        endpoint_url=settings.archive_s3_endpoint,
        region_name=settings.archive_s3_region,
        access_key_id=settings.archive_s3_access_key_id,
        secret_access_key=settings.archive_s3_secret_access_key,
    )
    payload = secrets.token_bytes(4096)
    digest = sha256(payload).hexdigest()
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    nonce = secrets.token_hex(8)
    prefix = settings.archive_s3_prefix.strip("/")
    key = "/".join(part for part in (prefix, "_smoke", f"{stamp}-{nonce}.bin") if part)

    uploaded = False
    try:
        client.put_object(
            Bucket=settings.archive_s3_bucket,
            Key=key,
            Body=payload,
            ContentLength=len(payload),
            ContentType="application/octet-stream",
            Metadata={"sha256": digest, "purpose": "transit-object-store-smoke"},
        )
        uploaded = True
        response = client.get_object(Bucket=settings.archive_s3_bucket, Key=key)
        body = response["Body"]
        try:
            downloaded = body.read()
        finally:
            body.close()
        remote_digest = sha256(downloaded).hexdigest()
        metadata = {str(k).lower(): str(v) for k, v in response.get("Metadata", {}).items()}
        passed = downloaded == payload and remote_digest == digest and metadata.get("sha256") == digest
        report = {
            "passed": passed,
            "storage_kind": settings.archive_storage_kind,
            "bucket": settings.archive_s3_bucket,
            "object_key": key,
            "bytes": len(payload),
            "sha256": digest,
            "evaluated_at": datetime.now(UTC).isoformat(),
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if passed else 2
    finally:
        if uploaded:
            client.delete_object(Bucket=settings.archive_s3_bucket, Key=key)


if __name__ == "__main__":
    raise SystemExit(main())
