from __future__ import annotations

from typing import Protocol

from app.modules.mobility.gtfs.models import GtfsRoutePage, GtfsStopPage


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
