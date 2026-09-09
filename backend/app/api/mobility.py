from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from app.api.deps import get_live_cache, get_position_repository
from app.modules.mobility.adapters.rio import RIO_AGENCY
from app.modules.mobility.models import VehiclePosition
from app.modules.mobility.ports import LivePositionCache, PositionRepository

router = APIRouter(prefix="/v1", tags=["mobility"])


@router.get("/routes/{route_id}/vehicles", response_model=list[VehiclePosition])
async def vehicles_by_route(
    route_id: Annotated[
        str,
        Path(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9._-]+$"),
    ],
    cache: Annotated[LivePositionCache, Depends(get_live_cache)],
) -> list[VehiclePosition]:
    positions = await cache.by_route(agency_id=RIO_AGENCY, route_id=route_id)
    return list(positions)


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
