from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

from app.api.health import router as health_router
from app.api.mobility import router as mobility_router
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    pool = None
    cache_client = None
    if settings.infrastructure_enabled:
        from app.infrastructure.postgres import (
            PostgresPositionRepository,
            create_postgres_pool,
        )
        from app.infrastructure.valkey import ValkeyLivePositionCache, create_valkey_client

        pool = await create_postgres_pool(settings.database_url)
        cache_client = await create_valkey_client(settings.cache_url)
        app.state.position_repository = PostgresPositionRepository(pool)
        app.state.live_cache = ValkeyLivePositionCache(
            cache_client,
            ttl_seconds=settings.live_position_ttl_seconds,
        )

    try:
        yield
    finally:
        if cache_client is not None:
            await cache_client.aclose()
        if pool is not None:
            await pool.close()


def create_app() -> FastAPI:
    docs_url = "/docs" if settings.api_docs_enabled and settings.app_env != "production" else None
    app = FastAPI(
        title="Transit Intelligence API",
        version="0.6.0",
        docs_url=docs_url,
        redoc_url=None,
        lifespan=lifespan,
    )

    if settings.allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.allowed_origins,
            allow_credentials=False,
            allow_methods=["GET"],
            allow_headers=["Accept", "Content-Type"],
        )

    app.include_router(health_router)
    app.include_router(mobility_router)
    app.mount("/metrics", make_asgi_app())
    return app


app = create_app()
