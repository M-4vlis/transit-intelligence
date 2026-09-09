from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class GtfsMemberManifest(BaseModel):
    model_config = ConfigDict(frozen=True)

    filename: str
    compressed_bytes: int = Field(ge=0)
    uncompressed_bytes: int = Field(ge=0)
    crc32: str = Field(pattern=r"^[0-9a-f]{8}$")
    columns: tuple[str, ...]


class GtfsSnapshotManifest(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: Literal["gtfs-snapshot-manifest/v1"] = "gtfs-snapshot-manifest/v1"
    snapshot_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_id: Literal["rio-smtr-gtfs"] = "rio-smtr-gtfs"
    source_url: str
    fetched_at: datetime
    license_spdx: Literal["CC-BY-4.0"] = "CC-BY-4.0"
    attribution: Literal["Secretaria Municipal de Transportes do Rio de Janeiro"] = (
        "Secretaria Municipal de Transportes do Rio de Janeiro"
    )
    compressed_bytes: int = Field(gt=0)
    uncompressed_bytes: int = Field(gt=0)
    member_count: int = Field(gt=0)
    service_calendar_files: tuple[str, ...]
    files: tuple[GtfsMemberManifest, ...]
