from datetime import UTC, datetime, timedelta

from app.modules.mobility.operations.models import IngestionRunSample, SoakThresholds
from app.modules.mobility.operations.soak import assess_soak


def _run(at: datetime, *, status: str = "success", fingerprint: str = "abc") -> IngestionRunSample:
    return IngestionRunSample(
        status=status,
        started_at=at - timedelta(seconds=1),
        finished_at=at,
        received_records=100,
        rejected_records=0,
        persisted_records=90,
        cached_records=90,
        contract_fingerprint=fingerprint,
    )


def test_soak_passes_healthy_window():
    now = datetime(2026, 9, 1, 12, tzinfo=UTC)
    runs = [_run(now - timedelta(seconds=i * 30)) for i in range(120)]
    result = assess_soak(
        runs,
        now=now,
        window=timedelta(hours=1),
        poll_interval_seconds=30,
        thresholds=SoakThresholds(
            min_cycle_coverage=0.90,
            min_success_ratio=0.98,
            max_gap_seconds=60,
            max_latest_age_seconds=60,
        ),
    )
    assert result.passed is True
    assert result.total_runs == 120
    assert result.reasons == ()


def test_soak_fails_when_success_ratio_is_low():
    now = datetime(2026, 9, 1, 12, tzinfo=UTC)
    runs = [_run(now - timedelta(seconds=i * 30)) for i in range(118)]
    runs.extend([
        _run(now - timedelta(seconds=118 * 30), status="failure"),
        _run(now - timedelta(seconds=119 * 30), status="failure"),
    ])
    result = assess_soak(
        runs,
        now=now,
        window=timedelta(hours=1),
        poll_interval_seconds=30,
        thresholds=SoakThresholds(min_success_ratio=0.99),
    )
    assert result.passed is False
    assert any(reason.startswith("success_ratio_low") for reason in result.reasons)


def test_soak_detects_contract_drift():
    now = datetime(2026, 9, 1, 12, tzinfo=UTC)
    runs = [_run(now - timedelta(seconds=i * 30), fingerprint="abc") for i in range(119)]
    runs.append(_run(now - timedelta(seconds=119 * 30), fingerprint="def"))
    result = assess_soak(
        runs,
        now=now,
        window=timedelta(hours=1),
        poll_interval_seconds=30,
        thresholds=SoakThresholds(),
    )
    assert result.passed is False
    assert "contract_drift:abc,def" in result.reasons


def test_soak_detects_stale_last_cycle_and_large_gap():
    now = datetime(2026, 9, 1, 12, tzinfo=UTC)
    runs = [_run(now - timedelta(minutes=10) - timedelta(seconds=i * 30)) for i in range(120)]
    result = assess_soak(
        runs,
        now=now,
        window=timedelta(hours=1),
        poll_interval_seconds=30,
        thresholds=SoakThresholds(max_latest_age_seconds=60),
    )
    assert result.passed is False
    assert any(reason.startswith("latest_run_stale") for reason in result.reasons)


def test_soak_requires_real_data_flow():
    now = datetime(2026, 9, 1, 12, tzinfo=UTC)
    runs = [
        IngestionRunSample(
            status="success",
            started_at=now - timedelta(seconds=i * 30 + 1),
            finished_at=now - timedelta(seconds=i * 30),
            received_records=0,
            rejected_records=0,
            persisted_records=0,
            cached_records=0,
            contract_fingerprint="abc",
        )
        for i in range(120)
    ]
    result = assess_soak(
        runs,
        now=now,
        window=timedelta(hours=1),
        poll_interval_seconds=30,
        thresholds=SoakThresholds(),
    )
    assert result.passed is False
    assert "no_source_records_received" in result.reasons
    assert "no_positions_persisted" in result.reasons
    assert "no_positions_cached" in result.reasons
