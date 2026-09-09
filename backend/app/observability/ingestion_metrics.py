from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

from app.modules.mobility.ingestion.service import IngestionReport

INGESTION_CYCLES = Counter(
    "transit_ingestion_cycles_total",
    "Completed ingestion cycles by source and outcome.",
    labelnames=("source", "outcome"),
)
INGESTION_RECORDS = Counter(
    "transit_ingestion_records_total",
    "Records observed by ingestion stage.",
    labelnames=("source", "stage"),
)
INGESTION_DURATION = Histogram(
    "transit_ingestion_cycle_duration_seconds",
    "End-to-end duration of an ingestion cycle.",
    labelnames=("source",),
    buckets=(0.25, 0.5, 1, 2, 4, 8, 16, 32, 64),
)
LAST_SUCCESS_UNIX = Gauge(
    "transit_ingestion_last_success_unixtime",
    "Unix timestamp of the latest successful ingestion cycle.",
    labelnames=("source",),
)
LAST_FAILURE_UNIX = Gauge(
    "transit_ingestion_last_failure_unixtime",
    "Unix timestamp of the latest failed ingestion cycle.",
    labelnames=("source",),
)
LEASE_CONTENTION = Counter(
    "transit_ingestion_lease_contention_total",
    "Number of cycles skipped because another collector held the distributed lease.",
    labelnames=("source",),
)
SOURCE_REJECTION_RATIO = Gauge(
    "transit_ingestion_source_rejection_ratio",
    "Fraction of received source records rejected by boundary validation.",
    labelnames=("source",),
)


def observe_success(report: IngestionReport) -> None:
    source = report.source
    duration = max(0.0, (report.finished_at - report.started_at).total_seconds())
    INGESTION_CYCLES.labels(source=source, outcome="success").inc()
    INGESTION_DURATION.labels(source=source).observe(duration)
    LAST_SUCCESS_UNIX.labels(source=source).set(report.finished_at.timestamp())

    stage_counts = {
        "received": report.received_records,
        "rejected": report.rejected_records,
        "deduplicated": report.deduplicated_records,
        "persisted": report.persisted_records,
        "cached": report.cached_records,
    }
    for stage, count in stage_counts.items():
        if count:
            INGESTION_RECORDS.labels(source=source, stage=stage).inc(count)

    ratio = (
        report.rejected_records / report.received_records if report.received_records else 0.0
    )
    SOURCE_REJECTION_RATIO.labels(source=source).set(ratio)


def observe_failure(*, source: str, unix_time: float) -> None:
    INGESTION_CYCLES.labels(source=source, outcome="failure").inc()
    LAST_FAILURE_UNIX.labels(source=source).set(unix_time)


def observe_lease_contention(*, source: str) -> None:
    LEASE_CONTENTION.labels(source=source).inc()
