from __future__ import annotations

import json
import os
import re
import secrets
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.infrastructure.parquet import create_s3_compatible_client

_STATE_NAME = ".object-storage-state.json"
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]+\.json$")
_MAX_FILE_BYTES = 16 * 1024 * 1024


def _digest(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def _remote_bytes(client: Any, *, bucket: str, key: str) -> tuple[bytes, dict[str, str]]:
    response = client.get_object(Bucket=bucket, Key=key)
    body = response["Body"]
    try:
        payload = body.read()
    finally:
        body.close()
    metadata = {str(k).lower(): str(v) for k, v in response.get("Metadata", {}).items()}
    return payload, metadata


def _put_verified(
    client: Any,
    *,
    bucket: str,
    key: str,
    payload: bytes,
    purpose: str,
) -> dict[str, object]:
    digest = _digest(payload)
    metadata = {"sha256": digest, "purpose": purpose}
    exists = False
    try:
        head = client.head_object(Bucket=bucket, Key=key)
        exists = True
    except client.exceptions.ClientError as exc:
        status = int(exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0))
        if status != 404:
            raise
    if exists:
        remote_metadata = {
            str(k).lower(): str(v) for k, v in head.get("Metadata", {}).items()
        }
        if int(head.get("ContentLength", -1)) != len(payload):
            raise RuntimeError(f"remote evidence size collision for {key}")
        if remote_metadata.get("sha256") != digest:
            raise RuntimeError(f"remote evidence hash collision for {key}")
    else:
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=payload,
            ContentLength=len(payload),
            ContentType="application/json" if key.endswith(".json") else "text/plain",
            Metadata=metadata,
        )
    downloaded, remote_metadata = _remote_bytes(client, bucket=bucket, key=key)
    if (
        len(downloaded) != len(payload)
        or _digest(downloaded) != digest
        or remote_metadata.get("sha256") != digest
    ):
        raise RuntimeError(f"remote evidence verification failed for {key}")
    return {
        "key": key,
        "byte_size": len(payload),
        "sha256": digest,
        "remote_read_verified": True,
        "preexisting": exists,
    }


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": 1, "files": {}}
    state = json.loads(path.read_text(encoding="utf-8"))
    if state.get("schema_version") != 1 or not isinstance(state.get("files"), dict):
        raise RuntimeError("invalid confidence evidence archive state")
    return state


def _evidence_files(directory: Path) -> list[Path]:
    prefixes = ("cohort-", "summary-", "calibration-")
    return sorted(
        path
        for path in directory.iterdir()
        if path.is_file()
        and not path.is_symlink()
        and path.name.startswith(prefixes)
        and _SAFE_NAME.fullmatch(path.name)
    )


def archive_evidence(
    *,
    client: Any,
    bucket: str,
    prefix: str,
    directory: Path,
    now: datetime,
) -> dict[str, object]:
    directory = directory.resolve(strict=True)
    state_path = directory / _STATE_NAME
    state = _load_state(state_path)
    state_files: dict[str, Any] = state["files"]
    base_key = "/".join(
        part for part in (prefix.strip("/"), "_m2-confidence") if part
    )
    uploaded = []
    skipped = 0
    for path in _evidence_files(directory):
        payload = path.read_bytes()
        if len(payload) > _MAX_FILE_BYTES:
            raise RuntimeError(f"confidence evidence exceeds size limit: {path.name}")
        digest = _digest(payload)
        previous = state_files.get(path.name)
        if previous is not None:
            if previous.get("sha256") != digest or previous.get("byte_size") != len(payload):
                raise RuntimeError(f"immutable confidence evidence changed: {path.name}")
            skipped += 1
            continue
        result = _put_verified(
            client,
            bucket=bucket,
            key=f"{base_key}/evidence/{path.name}",
            payload=payload,
            purpose="transit-m2-confidence-evidence",
        )
        result["local_name"] = path.name
        result["kind"] = path.name.split("-", 1)[0]
        uploaded.append(result)
        state_files[path.name] = {
            "key": result["key"],
            "byte_size": result["byte_size"],
            "sha256": result["sha256"],
            "verified_at": now.astimezone(UTC).isoformat(),
        }

    if not uploaded:
        return {
            "status": "no_change",
            "uploaded_count": 0,
            "skipped_count": skipped,
            "manifest_key": None,
        }

    stamp = now.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    nonce = secrets.token_hex(4)
    checksum_payload = (directory / "SHA256SUMS").read_bytes()
    checksum = _put_verified(
        client,
        bucket=bucket,
        key=f"{base_key}/checksums/SHA256SUMS-{stamp}-{nonce}.txt",
        payload=checksum_payload,
        purpose="transit-m2-confidence-checksums",
    )
    checksum["local_name"] = "SHA256SUMS"
    checksum["kind"] = "checksums"
    evidence_objects = [
        {
            "key": item["key"],
            "local_name": name,
            "kind": name.split("-", 1)[0],
            "byte_size": item["byte_size"],
            "sha256": item["sha256"],
            "remote_read_verified": True,
        }
        for name, item in sorted(state_files.items())
    ]
    objects = [*evidence_objects, checksum]
    manifest_payload = json.dumps(
        {
            "schema_version": 1,
            "created_at": now.astimezone(UTC).isoformat(),
            "objects": objects,
        },
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ).encode("utf-8")
    manifest_key = f"{base_key}/manifests/{stamp}-{nonce}.json"
    _put_verified(
        client,
        bucket=bucket,
        key=manifest_key,
        payload=manifest_payload,
        purpose="transit-m2-confidence-manifest",
    )

    state["updated_at"] = now.astimezone(UTC).isoformat()
    state["last_manifest_key"] = manifest_key
    temporary = directory / f"{_STATE_NAME}.{os.getpid()}.tmp"
    temporary.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(state_path)
    return {
        "status": "verified",
        "uploaded_count": len(uploaded),
        "skipped_count": skipped,
        "manifest_key": manifest_key,
        "manifest_object_count": len(objects),
    }


def main() -> None:
    settings.validate_archive_storage()
    directory = Path(os.environ.get("CONFIDENCE_EVIDENCE_DIR", "/evidence"))
    client = create_s3_compatible_client(
        endpoint_url=settings.archive_s3_endpoint,
        region_name=settings.archive_s3_region,
        access_key_id=settings.archive_s3_access_key_id,
        secret_access_key=settings.archive_s3_secret_access_key,
    )
    report = archive_evidence(
        client=client,
        bucket=settings.archive_s3_bucket,
        prefix=settings.archive_s3_prefix,
        directory=directory,
        now=datetime.now(UTC),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
