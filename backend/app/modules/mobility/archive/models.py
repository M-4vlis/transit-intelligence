from __future__ import annotations

from datetime import date
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field


class ArchiveStatus(StrEnum):
    WRITTEN = "written"
    VERIFIED = "verified"
    FAILED = "failed"


class ArchiveArtifact(BaseModel):
    source: str
    archive_day: date
    object_uri: str
    local_path: Path | None = None
    format: str = "parquet"
    row_count: int = Field(ge=0)
    byte_size: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ArchiveVerification(BaseModel):
    valid: bool
    row_count: int = Field(ge=0)
    byte_size: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    detail: str = ""


class ArchiveRunReport(BaseModel):
    source: str
    archive_day: date
    status: ArchiveStatus
    object_uri: str | None = None
    row_count: int = Field(default=0, ge=0)
    byte_size: int = Field(default=0, ge=0)
    sha256: str | None = None
    skipped_existing: bool = False
