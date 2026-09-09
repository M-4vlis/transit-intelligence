from __future__ import annotations

from datetime import date

from app.modules.mobility.archive.models import ArchiveRunReport, ArchiveStatus
from app.modules.mobility.archive.ports import (
    ArchiveManifestCatalog,
    ColdArchiveWriter,
    HistoricalPositionSource,
)


class ArchiveVerificationError(RuntimeError):
    """The cold archive was written but failed integrity verification."""


class ArchiveDayService:
    def __init__(
        self,
        *,
        source: str,
        historical_source: HistoricalPositionSource,
        writer: ColdArchiveWriter,
        catalog: ArchiveManifestCatalog,
        batch_size: int = 50_000,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        self.source = source
        self.historical_source = historical_source
        self.writer = writer
        self.catalog = catalog
        self.batch_size = batch_size

    async def run_day(self, *, day: date) -> ArchiveRunReport:
        if await self.catalog.is_verified(source=self.source, day=day):
            return ArchiveRunReport(
                source=self.source,
                archive_day=day,
                status=ArchiveStatus.VERIFIED,
                skipped_existing=True,
            )

        batches = self.historical_source.iter_day(
            source=self.source,
            day=day,
            batch_size=self.batch_size,
        )
        artifact = await self.writer.write_day(
            source=self.source,
            day=day,
            batches=batches,
        )
        await self.catalog.record_written(artifact)

        try:
            verification = await self.writer.verify(artifact)
            expected = (
                artifact.row_count,
                artifact.byte_size,
                artifact.sha256,
            )
            observed = (
                verification.row_count,
                verification.byte_size,
                verification.sha256,
            )
            if not verification.valid or observed != expected:
                detail = verification.detail or "archive integrity metadata mismatch"
                raise ArchiveVerificationError(detail)
            await self.catalog.mark_verified(artifact)
        except Exception as exc:
            await self.catalog.mark_failed(
                source=self.source,
                day=day,
                object_uri=artifact.object_uri,
                detail=str(exc)[:1000],
            )
            raise

        return ArchiveRunReport(
            source=self.source,
            archive_day=day,
            status=ArchiveStatus.VERIFIED,
            object_uri=artifact.object_uri,
            row_count=artifact.row_count,
            byte_size=artifact.byte_size,
            sha256=artifact.sha256,
        )
