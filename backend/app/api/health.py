from datetime import UTC, datetime

from fastapi import APIRouter, Request, Response, status

router = APIRouter(tags=["system"])


@router.get("/health/live", summary="Liveness probe")
def liveness() -> dict[str, str]:
    return {"status": "ok", "time": datetime.now(UTC).isoformat()}


@router.get("/health/ready", summary="Readiness probe")
async def readiness(request: Request, response: Response) -> dict[str, object]:
    cache = getattr(request.app.state, "live_cache", None)
    repository = getattr(request.app.state, "position_repository", None)
    checks = {"database": False, "cache": False}

    if repository is not None:
        try:
            checks["database"] = await repository.ping()
        except Exception:  # noqa: BLE001 - readiness must fail closed for any driver error
            checks["database"] = False
    if cache is not None:
        try:
            checks["cache"] = await cache.ping()
        except Exception:  # noqa: BLE001 - readiness must fail closed for any driver error
            checks["cache"] = False

    ready = all(checks.values())
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ready" if ready else "not_ready", "checks": checks}


@router.get("/health", include_in_schema=False)
def compatibility_health() -> dict[str, str]:
    return liveness()
