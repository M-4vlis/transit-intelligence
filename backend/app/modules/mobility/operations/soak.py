from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from itertools import pairwise

from app.modules.mobility.operations.models import (
    IngestionRunSample,
    SoakAssessment,
    SoakThresholds,
)


def assess_soak(
    runs: Sequence[IngestionRunSample],
    *,
    now: datetime,
    window: timedelta,
    poll_interval_seconds: float,
    thresholds: SoakThresholds,
) -> SoakAssessment:
    thresholds.validate()
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    if window.total_seconds() <= 0:
        raise ValueError("window must be positive")
    if poll_interval_seconds <= 0:
        raise ValueError("poll_interval_seconds must be positive")

    now = now.astimezone(UTC)
    window_start = now - window
    normalized = sorted(
        (
            item
            for item in runs
            if item.finished_at.astimezone(UTC) >= window_start
            and item.finished_at.astimezone(UTC) <= now
        ),
        key=lambda item: item.finished_at,
    )

    observed_hours = window.total_seconds() / 3600
    expected_runs = max(1, math.floor(window.total_seconds() / poll_interval_seconds))
    minimum_runs = max(1, math.floor(expected_runs * thresholds.min_cycle_coverage))
    total_runs = len(normalized)
    successful_runs = sum(item.status == "success" for item in normalized)
    failed_runs = total_runs - successful_runs
    success_ratio = successful_runs / total_runs if total_runs else 0.0

    total_received = sum(item.received_records for item in normalized)
    total_rejected = sum(item.rejected_records for item in normalized)
    rejection_ratio = total_rejected / total_received if total_received else 0.0
    total_persisted = sum(item.persisted_records for item in normalized)
    total_cached = sum(item.cached_records for item in normalized)
    fingerprints = tuple(
        sorted({item.contract_fingerprint for item in normalized if item.contract_fingerprint})
    )

    max_gap_seconds: float | None = None
    if len(normalized) >= 2:
        gaps = [
            (current.finished_at - previous.finished_at).total_seconds()
            for previous, current in pairwise(normalized)
        ]
        max_gap_seconds = max(gaps)

    latest_run_age_seconds: float | None = None
    if normalized:
        latest_run_age_seconds = (
            now - normalized[-1].finished_at.astimezone(UTC)
        ).total_seconds()

    reasons: list[str] = []
    if total_runs < minimum_runs:
        reasons.append(f"cycle_coverage_low:{total_runs}<{minimum_runs}")
    if success_ratio < thresholds.min_success_ratio:
        reasons.append(
            f"success_ratio_low:{success_ratio:.6f}<{thresholds.min_success_ratio:.6f}"
        )
    if total_received <= 0:
        reasons.append("no_source_records_received")
    if rejection_ratio > thresholds.max_rejection_ratio:
        reasons.append(
            f"rejection_ratio_high:{rejection_ratio:.6f}>{thresholds.max_rejection_ratio:.6f}"
        )
    if total_persisted <= 0:
        reasons.append("no_positions_persisted")
    if total_cached <= 0:
        reasons.append("no_positions_cached")
    if len(fingerprints) > thresholds.max_contract_fingerprints:
        reasons.append(
            "contract_drift:" + ",".join(fingerprints)
        )
    if max_gap_seconds is not None and max_gap_seconds > thresholds.max_gap_seconds:
        reasons.append(
            f"ingestion_gap_high:{max_gap_seconds:.3f}>{thresholds.max_gap_seconds:.3f}"
        )
    if latest_run_age_seconds is None:
        reasons.append("no_recent_ingestion_run")
    elif latest_run_age_seconds > thresholds.max_latest_age_seconds:
        reasons.append(
            "latest_run_stale:"
            f"{latest_run_age_seconds:.3f}>{thresholds.max_latest_age_seconds:.3f}"
        )

    return SoakAssessment(
        passed=not reasons,
        reasons=tuple(reasons),
        observed_hours=observed_hours,
        expected_runs=expected_runs,
        minimum_runs=minimum_runs,
        total_runs=total_runs,
        successful_runs=successful_runs,
        failed_runs=failed_runs,
        success_ratio=success_ratio,
        total_received_records=total_received,
        total_rejected_records=total_rejected,
        rejection_ratio=rejection_ratio,
        total_persisted_records=total_persisted,
        total_cached_records=total_cached,
        unique_contract_fingerprints=fingerprints,
        max_gap_seconds=max_gap_seconds,
        latest_run_age_seconds=latest_run_age_seconds,
    )
