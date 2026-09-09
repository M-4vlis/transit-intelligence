from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from datetime import date
from typing import Protocol

from app.modules.mobility.archive.models import ArchiveArtifact, ArchiveVerification
from app.modules.mobility.models import VehiclePosition


class HistoricalPositionSource(Protocol):
    def iter_day(
        self,
        *,
        source: str,
        day: date,
        batch_size: int,
    ) -> AsyncIterator[Sequence[VehiclePosition]]: ...


class ColdArchiveWriter(Protocol):
    async def write_day(
        self,
        *,
        source: str,
        day: date,
        batches: AsyncIterator[Sequence[VehiclePosition]],
    ) -> ArchiveArtifact: ...

    async def verify(self, artifact: ArchiveArtifact) -> ArchiveVerification: ...


class ArchiveManifestCatalog(Protocol):
    async def is_verified(self, *, source: str, day: date) -> bool: ...

    async def record_written(self, artifact: ArchiveArtifact) -> None: ...

    async def mark_verified(self, artifact: ArchiveArtifact) -> None: ...

    async def mark_failed(
        self,
        *,
        source: str,
        day: date,
        object_uri: str,
        detail: str,
    ) -> None: ...
