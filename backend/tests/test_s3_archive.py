from __future__ import annotations

from datetime import date
from hashlib import sha256
from io import BytesIO
from pathlib import Path

import pytest

from app.infrastructure.parquet import S3CompatibleParquetArchiveWriter, create_s3_compatible_client
from app.modules.mobility.archive.models import ArchiveArtifact


class FakeStreamingBody:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.closed = False

    def iter_chunks(self, chunk_size: int):
        for offset in range(0, len(self.payload), chunk_size):
            yield self.payload[offset : offset + chunk_size]

    def close(self) -> None:
        self.closed = True


class FakeS3Client:
    def __init__(self, payload: bytes, metadata: dict[str, str]) -> None:
        self.payload = payload
        self.metadata = metadata

    def get_object(self, *, Bucket: str, Key: str):
        assert Bucket == "archive-bucket"
        assert Key == "history/rio-smtr-gps/2026/09/2026-09-01.parquet"
        return {
            "Body": FakeStreamingBody(self.payload),
            "Metadata": self.metadata,
        }


@pytest.mark.asyncio
async def test_s3_remote_verification_checks_full_content_hash(tmp_path: Path) -> None:
    payload = b"parquet-bytes-for-test"
    digest = sha256(payload).hexdigest()
    client = FakeS3Client(payload, {"sha256": digest, "row-count": "12"})
    writer = S3CompatibleParquetArchiveWriter(
        client=client,
        bucket="archive-bucket",
        prefix="history",
        spool_root=tmp_path,
    )
    spool = tmp_path / "spool.parquet"
    spool.write_bytes(payload)
    artifact = ArchiveArtifact(
        source="rio-smtr-gps",
        archive_day=date(2026, 9, 1),
        object_uri="s3://archive-bucket/history/rio-smtr-gps/2026/09/2026-09-01.parquet",
        local_path=spool,
        row_count=12,
        byte_size=len(payload),
        sha256=digest,
    )

    verification = await writer.verify(artifact)

    assert verification.valid is True
    assert not spool.exists()


@pytest.mark.asyncio
async def test_s3_remote_verification_detects_corruption(tmp_path: Path) -> None:
    expected = b"expected"
    actual = b"corrupted"
    digest = sha256(expected).hexdigest()
    client = FakeS3Client(actual, {"sha256": digest, "row-count": "1"})
    writer = S3CompatibleParquetArchiveWriter(
        client=client,
        bucket="archive-bucket",
        prefix="history",
        spool_root=tmp_path,
    )
    artifact = ArchiveArtifact(
        source="rio-smtr-gps",
        archive_day=date(2026, 9, 1),
        object_uri="s3://archive-bucket/history/rio-smtr-gps/2026/09/2026-09-01.parquet",
        row_count=1,
        byte_size=len(expected),
        sha256=digest,
    )

    verification = await writer.verify(artifact)

    assert verification.valid is False
    assert verification.sha256 == sha256(actual).hexdigest()


def test_s3_object_key_is_stable() -> None:
    writer = S3CompatibleParquetArchiveWriter(
        client=object(),
        bucket="archive-bucket",
        prefix="history",
        spool_root=Path("/tmp/transit-spool"),
    )
    assert writer._object_key(source="rio-smtr-gps", day=date(2026, 9, 1)) == (
        "history/rio-smtr-gps/2026/09/2026-09-01.parquet"
    )


def test_s3_client_requires_https() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        create_s3_compatible_client(
            endpoint_url="http://object.example",
            region_name="region",
            access_key_id="access",
            secret_access_key="secret",
        )


def test_s3_client_uses_compatible_checksum_policy() -> None:
    client = create_s3_compatible_client(
        endpoint_url="https://object.example",
        region_name="region",
        access_key_id="access",
        secret_access_key="secret",
    )

    assert client.meta.config.request_checksum_calculation == "when_required"
    assert client.meta.config.response_checksum_validation == "when_required"
    assert client.meta.config.s3["addressing_style"] == "path"
