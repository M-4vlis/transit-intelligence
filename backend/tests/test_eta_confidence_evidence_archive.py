from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.archive_eta_confidence_evidence import archive_evidence
from scripts.restore_eta_confidence_evidence import restore_latest_evidence


class _ClientError(Exception):
    def __init__(self, status: int):
        self.response = {"ResponseMetadata": {"HTTPStatusCode": status}}


class _Body:
    def __init__(self, payload: bytes):
        self._stream = BytesIO(payload)

    def read(self) -> bytes:
        return self._stream.read()

    def iter_chunks(self, chunk_size: int):
        while chunk := self._stream.read(chunk_size):
            yield chunk

    def close(self) -> None:
        self._stream.close()


class _Paginator:
    def __init__(self, client: _FakeS3):
        self.client = client

    def paginate(self, *, Bucket: str, Prefix: str):
        del Bucket
        yield {
            "Contents": [
                {"Key": key}
                for key in sorted(self.client.objects)
                if key.startswith(Prefix)
            ]
        }


class _FakeS3:
    exceptions = SimpleNamespace(ClientError=_ClientError)

    def __init__(self):
        self.objects: dict[str, tuple[bytes, dict[str, str]]] = {}

    def head_object(self, *, Bucket: str, Key: str):
        del Bucket
        if Key not in self.objects:
            raise _ClientError(404)
        payload, metadata = self.objects[Key]
        return {"ContentLength": len(payload), "Metadata": metadata}

    def put_object(
        self,
        *,
        Bucket: str,
        Key: str,
        Body: bytes,
        ContentLength: int,
        ContentType: str,
        Metadata: dict[str, str],
    ):
        del Bucket, ContentType
        payload = bytes(Body)
        assert len(payload) == ContentLength
        self.objects[Key] = (payload, dict(Metadata))

    def get_object(self, *, Bucket: str, Key: str):
        del Bucket
        payload, metadata = self.objects[Key]
        return {"Body": _Body(payload), "Metadata": metadata}

    def get_paginator(self, name: str) -> _Paginator:
        assert name == "list_objects_v2"
        return _Paginator(self)


def _evidence(directory: Path) -> None:
    names = (
        "cohort-20260913T120000Z.json",
        "summary-20260913T120000Z.json",
        "calibration-20260913T120000Z.json",
    )
    for name in names:
        (directory / name).write_text("{}", encoding="utf-8")
    checksums = "".join(
        f"{sha256((directory / name).read_bytes()).hexdigest()}  {directory / name}\n"
        for name in names
    )
    (directory / "SHA256SUMS").write_text(checksums, encoding="utf-8")


def test_confidence_evidence_upload_is_incremental_and_restorable(tmp_path: Path) -> None:
    _evidence(tmp_path)
    client = _FakeS3()
    now = datetime(2026, 9, 13, 12, tzinfo=UTC)

    first = archive_evidence(
        client=client,
        bucket="transit",
        prefix="transit-history",
        directory=tmp_path,
        now=now,
    )

    assert first["status"] == "verified"
    assert first["uploaded_count"] == 3
    assert first["manifest_object_count"] == 4
    assert (tmp_path / ".object-storage-state.json").is_file()

    restored = restore_latest_evidence(
        client=client,
        bucket="transit",
        prefix="transit-history",
        destination=tmp_path / "restored",
    )

    assert restored["status"] == "verified"
    assert restored["restored_object_count"] == 4
    assert restored["checksum_verified_file_count"] == 3
    assert {item["kind"] for item in restored["objects"]} == {
        "cohort",
        "summary",
        "calibration",
        "checksums",
    }

    second = archive_evidence(
        client=client,
        bucket="transit",
        prefix="transit-history",
        directory=tmp_path,
        now=now,
    )
    assert second == {
        "status": "no_change",
        "uploaded_count": 0,
        "skipped_count": 3,
        "manifest_key": None,
    }


def test_confidence_evidence_archive_rejects_local_immutable_change(
    tmp_path: Path,
) -> None:
    _evidence(tmp_path)
    client = _FakeS3()
    now = datetime(2026, 9, 13, 12, tzinfo=UTC)
    archive_evidence(
        client=client,
        bucket="transit",
        prefix="transit-history",
        directory=tmp_path,
        now=now,
    )
    (tmp_path / "cohort-20260913T120000Z.json").write_text(
        '{"changed":true}', encoding="utf-8"
    )

    with pytest.raises(RuntimeError, match="immutable confidence evidence changed"):
        archive_evidence(
            client=client,
            bucket="transit",
            prefix="transit-history",
            directory=tmp_path,
            now=now,
        )
