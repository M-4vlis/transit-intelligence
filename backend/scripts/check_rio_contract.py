from __future__ import annotations

import asyncio
import json
import os

import httpx

from app.core.config import settings
from app.modules.mobility.adapters.rio import RioRealtimeAdapter
from app.modules.mobility.sources.http import (
    ResilientJsonClient,
    RetryPolicy,
    validate_external_source_url,
)


async def run() -> dict[str, object]:
    validate_external_source_url(
        settings.rio_realtime_url,
        allowed_hosts=settings.allowed_source_hosts,
    )
    timeout = httpx.Timeout(settings.source_timeout_seconds)
    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=False,
        trust_env=False,
    ) as client:
        adapter = RioRealtimeAdapter(
            client=ResilientJsonClient(
                client,
                policy=RetryPolicy(max_attempts=3, base_delay_seconds=0.5),
                max_response_bytes=settings.rio_realtime_max_response_bytes,
            ),
            url=settings.rio_realtime_url,
            initial_window_seconds=settings.rio_realtime_initial_window_seconds,
            overlap_seconds=settings.rio_realtime_overlap_seconds,
            max_window_seconds=settings.rio_realtime_max_window_seconds,
        )
        batch = await adapter.fetch_vehicle_positions()

    received = len(batch.positions) + len(batch.rejected)
    if received == 0 or not batch.positions:
        raise RuntimeError("Rio source returned no valid vehicle positions")
    rejection_ratio = len(batch.rejected) / received
    if rejection_ratio >= 0.05:
        raise RuntimeError(
            f"Rio source schema rejection ratio too high: {rejection_ratio:.2%}"
        )

    expected = {
        item.strip()
        for item in os.getenv("EXPECTED_RIO_CONTRACT_FINGERPRINTS", "").split(",")
        if item.strip()
    }
    if expected and batch.contract_fingerprint not in expected:
        raise RuntimeError(
            "Rio source contract fingerprint changed: "
            f"observed={batch.contract_fingerprint} expected={sorted(expected)}"
        )

    return {
        "source": batch.source,
        "received_records": received,
        "valid_records": len(batch.positions),
        "rejected_records": len(batch.rejected),
        "rejection_ratio": round(rejection_ratio, 6),
        "contract_fingerprint": batch.contract_fingerprint,
        "observed_fields": batch.observed_fields,
        "fetched_at": batch.fetched_at.isoformat(),
    }


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))
