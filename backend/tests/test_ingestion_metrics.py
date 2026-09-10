from datetime import UTC, datetime, timedelta

from app.modules.mobility.ingestion.service import IngestionReport
from app.observability.ingestion_metrics import (
    INGESTION_CYCLES,
    LAST_SUCCESS_UNIX,
    SOURCE_REJECTION_RATIO,
    observe_success,
)


def _sample_value(metric, name: str, labels: dict[str, str]) -> float:
    value = metric.labels(**labels)._value.get()
    assert isinstance(value, float)
    return value


def test_success_metrics_capture_rejection_ratio_and_timestamp() -> None:
    source = "metrics-test-source"
    started = datetime(2026, 9, 1, 13, 0, tzinfo=UTC)
    finished = started + timedelta(seconds=2)
    report = IngestionReport(
        source=source,
        started_at=started,
        finished_at=finished,
        received_records=10,
        rejected_records=2,
        deduplicated_records=1,
        persisted_records=7,
        cached_records=7,
        quality_counts={"good": 7},
    )

    before = _sample_value(INGESTION_CYCLES, "cycles", {"source": source, "outcome": "success"})
    observe_success(report)

    assert _sample_value(
        INGESTION_CYCLES, "cycles", {"source": source, "outcome": "success"}
    ) == before + 1
    assert SOURCE_REJECTION_RATIO.labels(source=source)._value.get() == 0.2
    assert LAST_SUCCESS_UNIX.labels(source=source)._value.get() == finished.timestamp()
