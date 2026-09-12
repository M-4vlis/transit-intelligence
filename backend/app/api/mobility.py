from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api.deps import get_gtfs_catalog, get_live_cache, get_position_repository
from app.modules.mobility.adapters.rio import RIO_AGENCY
from app.modules.mobility.gtfs.models import GtfsRoutePage, GtfsStopPage, VehicleJourneyMatch
from app.modules.mobility.gtfs.ports import GtfsCatalog
from app.modules.mobility.models import VehiclePosition
from app.modules.mobility.ports import LivePositionCache, PositionRepository

router = APIRouter(prefix="/v1", tags=["mobility"])

_SAFE_ID_PATTERN = r"^[A-Za-z0-9._-]+$"
_MAX_SHAPE_PROJECTION_DISTANCE_M = 250.0


@router.get("/routes", response_model=GtfsRoutePage)
async def search_routes(
    catalog: Annotated[GtfsCatalog, Depends(get_gtfs_catalog)],
    query: Annotated[str | None, Query(min_length=1, max_length=80)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
) -> GtfsRoutePage:
    return await catalog.search_routes(query=query, limit=limit, offset=offset)


@router.get("/stops/nearby", response_model=GtfsStopPage)
async def nearby_stops(
    latitude: Annotated[float, Query(ge=-90, le=90)],
    longitude: Annotated[float, Query(ge=-180, le=180)],
    catalog: Annotated[GtfsCatalog, Depends(get_gtfs_catalog)],
    radius_m: Annotated[int, Query(ge=50, le=5000)] = 800,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
) -> GtfsStopPage:
    return await catalog.nearby_stops(
        latitude=latitude,
        longitude=longitude,
        radius_m=radius_m,
        limit=limit,
        offset=offset,
    )


@router.get("/routes/{route_id}/vehicles", response_model=list[VehiclePosition])
async def vehicles_by_route(
    route_id: Annotated[
        str,
        Path(min_length=1, max_length=32, pattern=_SAFE_ID_PATTERN),
    ],
    cache: Annotated[LivePositionCache, Depends(get_live_cache)],
) -> list[VehiclePosition]:
    positions = await cache.by_route(agency_id=RIO_AGENCY, route_id=route_id)
    return list(positions)


@router.get(
    "/routes/{route_id}/vehicles/{vehicle_id}/upcoming-stops",
    response_model=VehicleJourneyMatch,
)
async def vehicle_upcoming_stops(
    route_id: Annotated[str, Path(min_length=1, max_length=32, pattern=_SAFE_ID_PATTERN)],
    vehicle_id: Annotated[str, Path(min_length=1, max_length=32, pattern=_SAFE_ID_PATTERN)],
    cache: Annotated[LivePositionCache, Depends(get_live_cache)],
    catalog: Annotated[GtfsCatalog, Depends(get_gtfs_catalog)],
    limit: Annotated[int, Query(ge=1, le=10)] = 5,
) -> VehicleJourneyMatch:
    positions = await cache.by_route(agency_id=RIO_AGENCY, route_id=route_id)
    position = next((item for item in positions if item.vehicle_id == vehicle_id), None)
    if position is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="live vehicle was not found on this route",
        )
    return await catalog.match_vehicle_to_upcoming_stops(
        position=position,
        limit=limit,
        max_projection_distance_m=_MAX_SHAPE_PROJECTION_DISTANCE_M,
    )


@router.get("/vehicles/nearby", response_model=list[VehiclePosition])
async def nearby_vehicles(
    latitude: Annotated[float, Query(ge=-90, le=90)],
    longitude: Annotated[float, Query(ge=-180, le=180)],
    repository: Annotated[PositionRepository, Depends(get_position_repository)],
    radius_m: Annotated[int, Query(ge=50, le=5000)] = 800,
    max_age_seconds: Annotated[int, Query(ge=30, le=600)] = 180,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[VehiclePosition]:
    positions = await repository.nearby(
        latitude=latitude,
        longitude=longitude,
        radius_m=radius_m,
        max_age_seconds=max_age_seconds,
        limit=limit,
    )
    return list(positions)
