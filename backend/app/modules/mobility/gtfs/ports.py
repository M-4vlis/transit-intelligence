from __future__ import annotations

from datetime import datetime
from typing import Protocol

from app.modules.mobility.gtfs.models import GtfsRoutePage, GtfsStopPage, VehicleJourneyMatch
from app.modules.mobility.models import VehiclePosition


class GtfsCatalog(Protocol):
    async def search_routes(
        self,
        *,
        query: str | None,
        limit: int,
        offset: int,
    ) -> GtfsRoutePage: ...

    async def nearby_stops(
        self,
        *,
        latitude: float,
        longitude: float,
        radius_m: int,
        limit: int,
        offset: int,
    ) -> GtfsStopPage: ...

    async def match_vehicle_to_upcoming_stops(
        self,
        *,
        position: VehiclePosition,
        limit: int,
        max_projection_distance_m: float,
        evaluated_at: datetime | None = None,
    ) -> VehicleJourneyMatch: ...
