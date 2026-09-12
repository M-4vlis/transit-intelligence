from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.modules.mobility.adapters.base import (
    TransitRealtimeAdapter,
    TransitSourceSchemaError,
    TransitSourceUnavailable,
)
from app.modules.mobility.models import RejectedSourceRecord, TransitBatch, VehiclePosition
from app.modules.mobility.sources.http import ResilientJsonClient

RIO_TZ = ZoneInfo("America/Sao_Paulo")
RIO_SOURCE = "rio-smtr-gps"
RIO_AGENCY = "br-rj-rio-smtr-sppo"


@dataclass(frozen=True, slots=True)
class RioRequestWindow:
    start_at: datetime
    end_at: datetime

    def query_params(self) -> dict[str, str]:
        # The official SMTR client sends UTC values as `YYYY-MM-DD+HH:MM:SS`.
        # Passing a space lets the HTTP client encode that representation safely.
        fmt = "%Y-%m-%d %H:%M:%S"
        return {
            "dataInicial": self.start_at.astimezone(UTC).strftime(fmt),
            "dataFinal": self.end_at.astimezone(UTC).strftime(fmt),
        }


class RioVehiclePositionRaw(BaseModel):
    """Tolerant boundary DTO for documented/current Rio GPS field variants."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id_veiculo: str = Field(validation_alias=AliasChoices("id_veiculo", "ordem", "vehicle_id"))
    servico: str = Field(validation_alias=AliasChoices("servico", "linha", "route_id"))
    sentido: str | None = None
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    velocidade: float | None = Field(
        default=None,
        validation_alias=AliasChoices("velocidade", "velocidade_instantanea", "speed"),
    )
    direcao: float | None = Field(
        default=None,
        validation_alias=AliasChoices("direcao", "bearing", "direction"),
    )
    route_id: str | None = None
    trip_id: str | None = None
    shape_id: str | None = None
    timestamp_gps: datetime = Field(
        validation_alias=AliasChoices(
            "timestamp_gps", "datetime", "datahora", "observed_at", "timestamp"
        )
    )

    @field_validator("id_veiculo", "servico", "route_id", "trip_id", "shape_id", mode="before")
    @classmethod
    def normalize_identifier(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        text = str(value).strip()
        return text or None

    @field_validator("velocidade", mode="before")
    @classmethod
    def normalize_speed(cls, value: Any) -> Any:
        if value in (None, ""):
            return None
        try:
            speed = float(value)
        except (TypeError, ValueError):
            return None
        return speed if speed >= 0 else None

    @field_validator("direcao", mode="before")
    @classmethod
    def normalize_bearing(cls, value: Any) -> Any:
        if value in (None, ""):
            return None
        try:
            bearing = float(value)
        except (TypeError, ValueError):
            return None
        return bearing if 0 <= bearing <= 360 else None

    @field_validator("timestamp_gps", mode="before")
    @classmethod
    def parse_rio_datetime(cls, value: Any) -> Any:
        if isinstance(value, datetime):
            return value
        if isinstance(value, (int, float)):
            epoch = float(value)
            if abs(epoch) > 10_000_000_000:
                epoch /= 1000.0
            return datetime.fromtimestamp(epoch, tz=UTC)
        if not isinstance(value, str):
            return value

        text = value.strip().replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            pass

        for fmt in (
            "%m-%d-%Y %H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%d/%m/%Y %H:%M:%S",
        ):
            try:
                return datetime.strptime(text, fmt).replace(tzinfo=RIO_TZ)
            except ValueError:
                continue
        return value

    def to_canonical(self, *, received_at: datetime | None = None) -> VehiclePosition:
        received_at = received_at or datetime.now(UTC)
        route_id = self.route_id or self.servico
        bearing = 0 if self.direcao == 360 else self.direcao

        observed_at = self.timestamp_gps
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=RIO_TZ)
        observed_at = observed_at.astimezone(UTC)

        return VehiclePosition(
            agency_id=RIO_AGENCY,
            vehicle_id=self.id_veiculo,
            route_id=route_id,
            trip_id=self.trip_id,
            shape_id=self.shape_id,
            latitude=self.latitude,
            longitude=self.longitude,
            speed_mps=(self.velocidade / 3.6) if self.velocidade is not None else None,
            bearing_deg=bearing,
            observed_at=observed_at,
            received_at=received_at,
            source=RIO_SOURCE,
        )


class RioRealtimeAdapter(TransitRealtimeAdapter):
    def __init__(
        self,
        *,
        client: ResilientJsonClient,
        url: str,
        initial_window_seconds: float = 120.0,
        overlap_seconds: float = 30.0,
        max_window_seconds: float = 300.0,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if initial_window_seconds <= 0:
            raise ValueError("initial_window_seconds must be positive")
        if overlap_seconds < 0:
            raise ValueError("overlap_seconds cannot be negative")
        if max_window_seconds <= 0:
            raise ValueError("max_window_seconds must be positive")
        if initial_window_seconds > max_window_seconds:
            raise ValueError("initial_window_seconds cannot exceed max_window_seconds")
        if overlap_seconds >= max_window_seconds:
            raise ValueError("overlap_seconds must be smaller than max_window_seconds")

        self.client = client
        self.url = url
        self.initial_window_seconds = initial_window_seconds
        self.overlap_seconds = overlap_seconds
        self.max_window_seconds = max_window_seconds
        self.clock = clock or (lambda: datetime.now(UTC))
        self._last_successful_window_end: datetime | None = None

    async def fetch_vehicle_positions(self) -> TransitBatch:
        window = self._next_request_window()
        fetched_at = window.end_at
        payload = await self.client.get_json(self.url, params=window.query_params())
        records = self._extract_records(payload)
        contract_fingerprint, observed_fields = self._contract_metadata(records)

        positions: list[VehiclePosition] = []
        rejected: list[RejectedSourceRecord] = []
        for record in records:
            try:
                raw = RioVehiclePositionRaw.model_validate(record)
                positions.append(raw.to_canonical(received_at=fetched_at))
            except ValidationError as exc:
                rejected.append(
                    RejectedSourceRecord.from_payload(
                        source=RIO_SOURCE,
                        payload=record,
                        reason_code="record_schema_invalid",
                        detail=self._compact_validation_error(exc),
                    )
                )

        if records and not positions:
            raise TransitSourceSchemaError(
                f"all {len(records)} Rio source records failed schema validation"
            )

        # Advance only after response and schema checks succeed. A transient
        # failure therefore retries from the previous successful cursor.
        self._last_successful_window_end = window.end_at

        return TransitBatch(
            source=RIO_SOURCE,
            fetched_at=fetched_at,
            positions=positions,
            rejected=rejected,
            contract_fingerprint=contract_fingerprint,
            observed_fields=observed_fields,
        )

    def _next_request_window(self) -> RioRequestWindow:
        now = self.clock()
        if now.tzinfo is None:
            raise ValueError("Rio adapter clock must return a timezone-aware datetime")
        end_at = now.astimezone(UTC).replace(microsecond=0)

        previous_end = self._last_successful_window_end
        if previous_end is None or previous_end >= end_at:
            start_at = end_at - timedelta(seconds=self.initial_window_seconds)
        else:
            start_at = previous_end - timedelta(seconds=self.overlap_seconds)

        earliest_allowed = end_at - timedelta(seconds=self.max_window_seconds)
        start_at = max(start_at, earliest_allowed)
        return RioRequestWindow(start_at=start_at, end_at=end_at)

    @staticmethod
    def _contract_metadata(records: list[Any]) -> tuple[str | None, list[str]]:
        fields = sorted(
            {str(key) for record in records[:500] if isinstance(record, dict) for key in record}
        )
        if not fields:
            return None, []
        fingerprint = sha256("\n".join(fields).encode("utf-8")).hexdigest()
        return fingerprint, fields

    @staticmethod
    def _extract_records(payload: Any) -> list[Any]:
        if isinstance(payload, list):
            return payload
        if not isinstance(payload, dict):
            raise TransitSourceSchemaError("Rio source root must be an object or array")

        # The official endpoint historically returns HTTP 200 even for some application-level
        # errors. Do not misclassify those envelopes as schema drift.
        if payload.get("RetornoOK") is False:
            detail = str(payload.get("DescricaoErro") or "unknown Rio source error")[:500]
            raise TransitSourceUnavailable(f"Rio source returned error envelope: {detail}")

        # Legacy Data.Rio responses used a columnar structure:
        # {"COLUMNS": ["DATAHORA", "ORDEM", ...], "DATA": [[...], ...]}.
        columns = payload.get("COLUMNS") or payload.get("columns")
        rows = payload.get("DATA") if "DATA" in payload else payload.get("data")
        if (
            isinstance(columns, list)
            and isinstance(rows, list)
            and (not rows or isinstance(rows[0], list))
        ):
            normalized_columns = [str(column).strip().lower() for column in columns]
            return [
                dict(zip(normalized_columns, row, strict=False))
                for row in rows
                if isinstance(row, list)
            ]

        for key in ("veiculos", "vehicles", "records", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return value

        data = payload.get("data")
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("veiculos", "vehicles", "records", "items"):
                value = data.get(key)
                if isinstance(value, list):
                    return value

        raise TransitSourceSchemaError("Rio source payload does not expose a known record list")

    @staticmethod
    def _compact_validation_error(exc: ValidationError) -> str:
        items = []
        for error in exc.errors(include_url=False)[:5]:
            loc = ".".join(str(part) for part in error.get("loc", ()))
            items.append(f"{loc}:{error.get('type', 'validation_error')}")
        return ";".join(items) or json.dumps(exc.errors(include_url=False), default=str)[:1000]
