from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from app.modules.mobility.models import RejectedSourceRecord, VehiclePosition


class PositionRepository(Protocol):
    async def save_many(self, positions: Sequence[VehiclePosition]) -> int: ...

    async def nearby(
        self,
        *,
        latitude: float,
        longitude: float,
        radius_m: int,
        max_age_seconds: int,
        limit: int,
    ) -> Sequence[VehiclePosition]: ...

    async def ping(self) -> bool: ...


class QuarantineRepository(Protocol):
    async def save_many(self, records: Sequence[RejectedSourceRecord]) -> int: ...


class LivePositionCache(Protocol):
    async def put_many(self, positions: Sequence[VehiclePosition]) -> int: ...

    async def by_route(self, *, agency_id: str, route_id: str) -> Sequence[VehiclePosition]: ...

    async def ping(self) -> bool: ...


class LeaseManager(Protocol):
    async def try_acquire(self, *, name: str, token: str, ttl_ms: int) -> bool: ...

    async def release(self, *, name: str, token: str) -> None: ...
