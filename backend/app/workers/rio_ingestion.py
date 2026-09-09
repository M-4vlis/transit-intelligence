from __future__ import annotations

import asyncio
import json
import logging
import secrets
from dataclasses import asdict
from datetime import UTC, datetime

import httpx
from prometheus_client import start_http_server

from app.core.config import settings
from app.infrastructure.postgres import (
    PostgresIngestionRunRepository,
    PostgresPositionRepository,
    PostgresQuarantineRepository,
    create_postgres_pool,
)
from app.infrastructure.valkey import ValkeyLivePositionCache, create_valkey_client
from app.modules.mobility.adapters.rio import RIO_SOURCE, RioRealtimeAdapter
from app.modules.mobility.ingestion.service import IngestionService
from app.modules.mobility.sources.http import (
    ResilientJsonClient,
    RetryPolicy,
    validate_external_source_url,
)
from app.observability.ingestion_metrics import (
    observe_failure,
    observe_lease_contention,
    observe_success,
)

logger = logging.getLogger("rio_ingestion")


def remaining_poll_delay(*, elapsed_seconds: float, poll_interval_seconds: float) -> float:
    if poll_interval_seconds <= 0:
        raise ValueError("poll_interval_seconds must be positive")
    return max(0.0, poll_interval_seconds - max(0.0, elapsed_seconds))


async def run() -> None:
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(message)s")
    validate_external_source_url(
        settings.rio_realtime_url, allowed_hosts=settings.allowed_source_hosts
    )
    start_http_server(settings.worker_metrics_port, addr="0.0.0.0")
    logger.info("worker_metrics_listening port=%s", settings.worker_metrics_port)
    pool = await create_postgres_pool(settings.database_url)
    cache_client = await create_valkey_client(settings.cache_url)
    cache = ValkeyLivePositionCache(cache_client, ttl_seconds=settings.live_position_ttl_seconds)
    repository = PostgresPositionRepository(pool)
    quarantine = PostgresQuarantineRepository(pool)
    ingestion_runs = PostgresIngestionRunRepository(pool)

    timeout = httpx.Timeout(settings.source_timeout_seconds)
    async with httpx.AsyncClient(
        timeout=timeout, follow_redirects=False, trust_env=False
    ) as http_client:
        source_client = ResilientJsonClient(
            http_client,
            policy=RetryPolicy(max_attempts=4, base_delay_seconds=0.5, max_delay_seconds=8),
            max_response_bytes=settings.rio_realtime_max_response_bytes,
        )
        adapter = RioRealtimeAdapter(
            client=source_client,
            url=settings.rio_realtime_url,
            initial_window_seconds=settings.rio_realtime_initial_window_seconds,
            overlap_seconds=settings.rio_realtime_overlap_seconds,
            max_window_seconds=settings.rio_realtime_max_window_seconds,
        )
        service = IngestionService(
            adapter=adapter,
            repository=repository,
            quarantine=quarantine,
            cache=cache,
        )

        lease_token = secrets.token_urlsafe(24)
        worst_case_request_seconds = (
            settings.source_timeout_seconds * 4 + 0.5 + 1 + 2 + 4 + 5
        )
        lease_ttl_ms = int(
            max(60.0, settings.rio_poll_interval_seconds + worst_case_request_seconds) * 1000
        )

        try:
            while True:
                acquired = await cache.try_acquire(
                    name="rio-realtime-ingestion",
                    token=lease_token,
                    ttl_ms=lease_ttl_ms,
                )
                if acquired:
                    cycle_started_at = datetime.now(UTC)
                    cycle_started_monotonic = asyncio.get_running_loop().time()
                    try:
                        report = await service.run_once()
                        await ingestion_runs.record(report)
                        observe_success(report)
                        logger.info("ingestion_batch %s", json.dumps(asdict(report), default=str))
                        if (
                            report.received_records
                            and report.rejected_records / report.received_records >= 0.05
                        ):
                            logger.warning(
                                "source_schema_rejection_ratio source=%s rejected=%s received=%s",
                                report.source,
                                report.rejected_records,
                                report.received_records,
                            )
                    except Exception as exc:
                        try:
                            await ingestion_runs.record_failure(
                                source=RIO_SOURCE,
                                started_at=cycle_started_at,
                                error=exc,
                            )
                        except Exception:
                            logger.exception("failed to persist ingestion failure telemetry")
                        observe_failure(source=RIO_SOURCE, unix_time=datetime.now(UTC).timestamp())
                        logger.exception("rio ingestion cycle failed")
                    try:
                        # Keep cadence anchored to cycle start. Network latency must not be
                        # added on top of the configured polling interval. The lease remains
                        # held through the remaining window so another worker cannot duplicate
                        # the source fetch.
                        elapsed = asyncio.get_running_loop().time() - cycle_started_monotonic
                        await asyncio.sleep(
                            remaining_poll_delay(
                                elapsed_seconds=elapsed,
                                poll_interval_seconds=settings.rio_poll_interval_seconds,
                            )
                        )
                    finally:
                        await cache.release(name="rio-realtime-ingestion", token=lease_token)
                else:
                    observe_lease_contention(source=RIO_SOURCE)
                    await asyncio.sleep(settings.rio_poll_interval_seconds)
        finally:
            await cache_client.aclose()
            await pool.close()


if __name__ == "__main__":
    asyncio.run(run())
