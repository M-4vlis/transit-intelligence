from fastapi import HTTPException, Request, status

from app.modules.mobility.gtfs.ports import GtfsCatalog
from app.modules.mobility.ports import LivePositionCache, PositionRepository


def get_live_cache(request: Request) -> LivePositionCache:
    cache = getattr(request.app.state, "live_cache", None)
    if cache is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="live mobility cache is not configured",
        )
    return cache


def get_position_repository(request: Request) -> PositionRepository:
    repository = getattr(request.app.state, "position_repository", None)
    if repository is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="mobility repository is not configured",
        )
    return repository


def get_gtfs_catalog(request: Request) -> GtfsCatalog:
    catalog = getattr(request.app.state, "gtfs_catalog", None)
    if catalog is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GTFS catalog is not configured",
        )
    return catalog
