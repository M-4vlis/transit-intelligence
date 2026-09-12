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


class GtfsImportResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    snapshot_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    active: bool
    already_imported: bool = False
    row_counts: dict[str, int]


class GtfsStopDistanceRehydrationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    snapshot_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    staged_rows: int = Field(gt=0)
    source_non_null_rows: int = Field(gt=0)
    updated_rows: int = Field(ge=0)
    target_non_null_rows: int = Field(gt=0)


class GtfsRoute(BaseModel):
    model_config = ConfigDict(frozen=True)

    snapshot_id: str
    route_id: str
    agency_id: str | None = None
    route_short_name: str | None = None
    route_long_name: str | None = None
    route_desc: str | None = None
    route_type: int
    route_color: str | None = None
    route_text_color: str | None = None


class GtfsRoutePage(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: tuple[GtfsRoute, ...]
    limit: int
    offset: int
    total: int


class NearbyGtfsStop(BaseModel):
    model_config = ConfigDict(frozen=True)

    snapshot_id: str
    stop_id: str
    stop_code: str | None = None
    stop_name: str
    stop_desc: str | None = None
    latitude: float
    longitude: float
    location_type: int | None = None
    parent_station: str | None = None
    wheelchair_boarding: int | None = None
    distance_m: float = Field(ge=0)


class GtfsStopPage(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: tuple[NearbyGtfsStop, ...]
    limit: int
    offset: int
    total: int
