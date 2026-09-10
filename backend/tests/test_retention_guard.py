from datetime import date

import pytest

from app.modules.mobility.archive.models import ArchiveArtifact, ArchiveVerification
from app.modules.mobility.retention.guard import RemoteVerifiedArchiveGuard

DAY = date(2026, 9, 1)
SHA = "a" * 64


class Catalog:
    def __init__(self, artifact):
        self.artifact = artifact

    async def get_verified(self, *, source, day):
        return self.artifact


class Writer:
    def __init__(self, *, valid=True, fail=False):
        self.valid = valid
        self.fail = fail

    async def verify(self, artifact):
        if self.fail:
            raise RuntimeError("storage unavailable")
        return ArchiveVerification(
            valid=self.valid,
            row_count=artifact.row_count,
            byte_size=artifact.byte_size,
            sha256=artifact.sha256 if self.valid else "b" * 64,
        )


def artifact():
    return ArchiveArtifact(
        source="rio-smtr-gps",
        archive_day=DAY,
        object_uri="s3://bucket/day.parquet",
        row_count=10,
        byte_size=100,
        sha256=SHA,
    )


@pytest.mark.asyncio
async def test_remote_guard_accepts_only_matching_live_verification() -> None:
    guard = RemoteVerifiedArchiveGuard(catalog=Catalog(artifact()), writer=Writer())
    assert await guard.is_verified(source="rio-smtr-gps", day=DAY) is True


@pytest.mark.asyncio
async def test_remote_guard_fails_closed_on_missing_or_corrupt_archive() -> None:
    missing = RemoteVerifiedArchiveGuard(catalog=Catalog(None), writer=Writer())
    corrupt = RemoteVerifiedArchiveGuard(catalog=Catalog(artifact()), writer=Writer(valid=False))
    assert await missing.is_verified(source="rio-smtr-gps", day=DAY) is False
    assert await corrupt.is_verified(source="rio-smtr-gps", day=DAY) is False


@pytest.mark.asyncio
async def test_remote_guard_fails_closed_when_storage_is_unavailable() -> None:
    guard = RemoteVerifiedArchiveGuard(catalog=Catalog(artifact()), writer=Writer(fail=True))
    assert await guard.is_verified(source="rio-smtr-gps", day=DAY) is False


@pytest.mark.asyncio
async def test_remote_guard_requires_hot_row_count_match() -> None:
    guard = RemoteVerifiedArchiveGuard(catalog=Catalog(artifact()), writer=Writer())
    assert (
        await guard.is_verified(
            source="rio-smtr-gps",
            day=DAY,
            expected_row_count=11,
        )
        is False
    )
