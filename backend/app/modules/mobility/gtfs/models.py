from __future__ import annotations

from datetime import datetime
from enum import StrEnum
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
    source_null_rows: int = Field(ge=0)
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


class JourneyMatchMethod(StrEnum):
    EXACT_TRIP = "exact_trip"
    ROUTE_SHAPE_PATTERN = "route_shape_pattern"


class JourneyUnavailableReason(StrEnum):
    MISSING_SHAPE_ID = "missing_shape_id"
    ROUTE_SHAPE_NOT_FOUND = "route_shape_not_found"
    SHAPE_PROJECTION_FAILED = "shape_projection_failed"
    VEHICLE_OFF_SHAPE = "vehicle_off_shape"
    NO_UPCOMING_STOPS = "no_upcoming_stops"


class EtaMethod(StrEnum):
    VEHICLE_RECENT_SPEED = "vehicle_recent_speed"
    HISTORICAL_SEGMENT_TIME_BAND = "historical_segment_time_band"
    ROUTE_SHAPE_RECENT_SPEED = "route_shape_recent_speed"


class EtaConfidence(StrEnum):
    EXPERIMENTAL = "experimental"


class EtaUnavailableReason(StrEnum):
    STALE_POSITION = "stale_position"
    INSUFFICIENT_SPEED_EVIDENCE = "insufficient_speed_evidence"
    DISTANCE_OUT_OF_RANGE = "distance_out_of_range"


class EtaEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    method: EtaMethod
    confidence: EtaConfidence = EtaConfidence.EXPERIMENTAL
    sample_count: int = Field(gt=0)
    window_seconds: int = Field(gt=0)
    speed_p25_mps: float = Field(gt=0)
    speed_median_mps: float = Field(gt=0)
    speed_p75_mps: float = Field(gt=0)


class UpcomingGtfsStop(BaseModel):
    model_config = ConfigDict(frozen=True)

    stop_id: str
    stop_name: str
    latitude: float
    longitude: float
    stop_sequence: int = Field(ge=0)
    shape_dist_traveled: float = Field(ge=0)
    shape_distance_ahead: float = Field(ge=0)
    estimated_arrival_at: datetime | None = None
    eta_seconds: int | None = Field(default=None, ge=0)
    eta_lower_seconds: int | None = Field(default=None, ge=0)
    eta_upper_seconds: int | None = Field(default=None, ge=0)
    eta_unavailable_reason: EtaUnavailableReason | None = None


class VehicleJourneyMatch(BaseModel):
    model_config = ConfigDict(frozen=True)

    available: bool
    unavailable_reason: JourneyUnavailableReason | None = None
    snapshot_id: str | None = None
    vehicle_id: str
    route_id: str
    source_trip_id: str | None = None
    matched_trip_id: str | None = None
    shape_id: str | None = None
    match_method: JourneyMatchMethod | None = None
    observed_at: datetime
    evaluated_at: datetime | None = None
    position_age_seconds: float | None = Field(default=None, ge=0)
    projected_shape_dist_traveled: float | None = Field(default=None, ge=0)
    projection_distance_m: float | None = Field(default=None, ge=0)
    eta_evidence: EtaEvidence | None = None
    eta_unavailable_reason: EtaUnavailableReason | None = None
    upcoming_stops: tuple[UpcomingGtfsStop, ...] = ()
