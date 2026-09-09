from __future__ import annotations

from datetime import date
import logging

from app.modules.mobility.archive.ports import ColdArchiveWriter

logger = logging.getLogger(__name__)


class RemoteVerifiedArchiveGuard:
    """Fail-closed guard requiring DB manifest, hot parity and live remote verification."""

    def __init__(self, *, catalog, writer: ColdArchiveWriter) -> None:
        self.catalog = catalog
        self.writer = writer

    async def is_verified(
        self,
        *,
        source: str,
        day: date,
        expected_row_count: int | None = None,
    ) -> bool:
        try:
            artifact = await self.catalog.get_verified(source=source, day=day)
            if artifact is None:
                return False
            if expected_row_count is not None and artifact.row_count != expected_row_count:
                logger.error(
                    "archive row count differs from hot partition source=%s day=%s "
                    "archive_rows=%s hot_rows=%s",
                    source,
                    day,
                    artifact.row_count,
                    expected_row_count,
                )
                return False
            verification = await self.writer.verify(artifact)
            return bool(
                verification.valid
                and verification.row_count == artifact.row_count
                and verification.byte_size == artifact.byte_size
                and verification.sha256 == artifact.sha256
            )
        except Exception:
            logger.exception("remote archive re-verification failed source=%s day=%s", source, day)
            return False
