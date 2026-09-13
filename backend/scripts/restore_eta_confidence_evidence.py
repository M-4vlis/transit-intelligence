from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.infrastructure.parquet import create_s3_compatible_client

_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]+$")


def _download(client: Any, *, bucket: str, key: str, target: Path) -> dict[str, object]:
    response = client.get_object(Bucket=bucket, Key=key)
    body = response["Body"]
    digest = sha256()
    size = 0
    try:
        with target.open("wb") as handle:
            for chunk in body.iter_chunks(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
    finally:
        body.close()
    metadata = {str(k).lower(): str(v) for k, v in response.get("Metadata", {}).items()}
    return {"byte_size": size, "sha256": digest.hexdigest(), "metadata": metadata}


def _latest_manifest_key(client: Any, *, bucket: str, prefix: str) -> str:
    keys = []
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        keys.extend(str(item["Key"]) for item in page.get("Contents", []))
    if not keys:
        raise RuntimeError("no remote confidence evidence manifest found")
    return max(keys)


def restore_latest_evidence(
    *,
    client: Any,
    bucket: str,
    prefix: str,
    destination: Path,
) -> dict[str, object]:
    destination.mkdir(parents=True, exist_ok=True)
    manifest_prefix = "/".join(
        part
        for part in (prefix.strip("/"), "_m2-confidence", "manifests/")
        if part
    )
    manifest_key = _latest_manifest_key(
        client,
        bucket=bucket,
        prefix=manifest_prefix,
    )
    manifest_path = destination / "manifest.json"
    manifest_download = _download(
        client,
        bucket=bucket,
        key=manifest_key,
        target=manifest_path,
    )
    metadata = manifest_download["metadata"]
    if metadata.get("sha256") != manifest_download["sha256"]:
        raise RuntimeError("remote confidence manifest metadata hash mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1 or not isinstance(manifest.get("objects"), list):
        raise RuntimeError("invalid remote confidence evidence manifest")

    restored = []
    for index, expected in enumerate(manifest["objects"]):
        key = str(expected["key"])
        local_name = str(expected.get("local_name", f"object-{index:04d}"))
        if not _SAFE_NAME.fullmatch(local_name) or local_name in {".", ".."}:
            raise RuntimeError(f"unsafe confidence evidence name: {local_name}")
        target = destination / local_name
        actual = _download(client, bucket=bucket, key=key, target=target)
        if (
            actual["byte_size"] != int(expected["byte_size"])
            or actual["sha256"] != expected["sha256"]
            or actual["metadata"].get("sha256") != expected["sha256"]
        ):
            raise RuntimeError(f"restored confidence evidence mismatch for {key}")
        restored.append(
            {
                "key": key,
                "local_name": local_name,
                "kind": expected["kind"],
                "byte_size": actual["byte_size"],
                "sha256": actual["sha256"],
            }
        )

    checksum_path = destination / "SHA256SUMS"
    if not checksum_path.is_file():
        raise RuntimeError("restored confidence evidence has no SHA256SUMS")
    expected_checksums: dict[str, str] = {}
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            raise RuntimeError("invalid restored SHA256SUMS line")
        digest, recorded_path = parts
        recorded_path = recorded_path.lstrip("* ")
        name = Path(recorded_path).name
        if not _SAFE_NAME.fullmatch(name):
            raise RuntimeError(f"unsafe checksum evidence name: {recorded_path}")
        previous_digest = expected_checksums.get(name)
        if previous_digest is not None and previous_digest != digest:
            raise RuntimeError(f"conflicting checksums for confidence evidence: {name}")
        expected_checksums[name] = digest
    checked_files = 0
    for item in restored:
        local_name = str(item["local_name"])
        if local_name == "SHA256SUMS":
            continue
        expected_digest = expected_checksums.get(local_name)
        if expected_digest != item["sha256"]:
            raise RuntimeError(f"checksum manifest mismatch for {local_name}")
        checked_files += 1
    return {
        "status": "verified",
        "verified_at": datetime.now(UTC).isoformat(),
        "manifest_key": manifest_key,
        "manifest_sha256": manifest_download["sha256"],
        "restored_object_count": len(restored),
        "restored_bytes": sum(int(item["byte_size"]) for item in restored),
        "checksum_verified_file_count": checked_files,
        "objects": restored,
    }


def main() -> None:
    settings.validate_archive_storage()
    client = create_s3_compatible_client(
        endpoint_url=settings.archive_s3_endpoint,
        region_name=settings.archive_s3_region,
        access_key_id=settings.archive_s3_access_key_id,
        secret_access_key=settings.archive_s3_secret_access_key,
    )
    with tempfile.TemporaryDirectory(prefix="transit-confidence-restore-") as temporary:
        report = restore_latest_evidence(
            client=client,
            bucket=settings.archive_s3_bucket,
            prefix=settings.archive_s3_prefix,
            destination=Path(temporary),
        )
    output = os.environ.get("CONFIDENCE_RESTORE_REPORT")
    if output:
        Path(output).write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
