from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from typing import Any

from pydantic import BaseModel, Field


class QualityStatus(StrEnum):
    GOOD = "good"
    DEGRADED = "degraded"
    STALE = "stale"
    INVALID = "invalid"


class VehiclePosition(BaseModel):
    agency_id: str
    vehicle_id: str
    route_id: str
    trip_id: str | None = None
    shape_id: str | None = None
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    speed_mps: float | None = Field(default=None, ge=0)
    bearing_deg: float | None = Field(default=None, ge=0, lt=360)
    observed_at: datetime
    received_at: datetime
    source: str
    quality_status: QualityStatus = QualityStatus.GOOD
    quality_score: float = Field(default=1.0, ge=0, le=1)

    def dedupe_key(self) -> str:
        observed = self.observed_at
        if observed.tzinfo is None:
            observed = observed.replace(tzinfo=UTC)
        observed = observed.astimezone(UTC)
        canonical = "|".join(
            (
                self.agency_id,
                self.vehicle_id,
                self.route_id,
                self.trip_id or "",
                observed.isoformat(timespec="milliseconds"),
                f"{self.latitude:.6f}",
                f"{self.longitude:.6f}",
            )
        )
        return sha256(canonical.encode("utf-8")).hexdigest()


class RejectedSourceRecord(BaseModel):
    source: str
    payload_hash: str
    reason_code: str
    detail: str = Field(max_length=1000)
    raw_payload: dict[str, Any] | list[Any] | str | int | float | bool | None = None

    @classmethod
    def from_payload(
        cls,
        *,
        source: str,
        payload: Any,
        reason_code: str,
        detail: str,
    ) -> RejectedSourceRecord:
        try:
            encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
        except TypeError:
            encoded = repr(payload)
        return cls(
            source=source,
            payload_hash=sha256(encoded.encode("utf-8")).hexdigest(),
            reason_code=reason_code,
            detail=detail[:1000],
            raw_payload=(
                payload if isinstance(payload, (dict, list, str, int, float, bool)) else None
            ),
        )


class TransitBatch(BaseModel):
    source: str
    fetched_at: datetime
    positions: list[VehiclePosition] = Field(default_factory=list)
    rejected: list[RejectedSourceRecord] = Field(default_factory=list)
    contract_fingerprint: str | None = None
    observed_fields: list[str] = Field(default_factory=list)
