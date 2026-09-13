from datetime import UTC, datetime

from scripts.measure_m2_resource_budget import build_resource_budget_report


def test_resource_budget_passes_with_large_safety_margin() -> None:
    report = build_resource_budget_report(
        generated_at=datetime(2026, 9, 13, tzinfo=UTC),
        host={
            "logical_cpus": 2,
            "memory_total_bytes": 12 * 1024**3,
            "memory_available_bytes": 8 * 1024**3,
            "root_total_bytes": 50 * 1024**3,
            "root_used_bytes": 10 * 1024**3,
            "project_bytes": 2 * 1024**3,
        },
        containers=[
            {
                "name": "transit-intelligence-api-1",
                "cpu_percent": 2.5,
                "memory_used_bytes": 200 * 1024**2,
                "memory_percent": 2.0,
            }
        ],
        object_storage={
            "object_count": 100,
            "byte_size": 100 * 1024**2,
            "m2_evidence_object_count": 30,
            "m2_evidence_bytes": 2 * 1024**2,
            "complete_parquet_object_count": 5,
            "complete_parquet_bytes": 500 * 1024**2,
        },
    )

    assert report["status"] == "passed"
    assert report["failures"] == []
    assert report["warnings"] == []
    assert report["object_storage"]["projected_m2_api_requests_per_month"] < 30_000
    assert report["limits"]["tenancy_wide_usage_not_observed"] is True


def test_resource_budget_fails_before_free_tier_is_exhausted() -> None:
    report = build_resource_budget_report(
        generated_at=datetime(2026, 9, 13, tzinfo=UTC),
        host={
            "logical_cpus": 4,
            "memory_total_bytes": 24 * 1024**3,
            "memory_available_bytes": 1024**3,
            "root_total_bytes": 50 * 1024**3,
            "root_used_bytes": 45 * 1024**3,
            "project_bytes": 12 * 1024**3,
        },
        containers=[],
        object_storage={
            "object_count": 10_000,
            "byte_size": 9 * 1024**3,
            "m2_evidence_object_count": 2_000,
            "m2_evidence_bytes": 1024**3,
            "complete_parquet_object_count": 5,
            "complete_parquet_bytes": 2 * 1024**3,
        },
    )

    assert report["status"] == "failed"
    assert "compute_shape_within_always_free" in report["failures"]
    assert "projected_object_storage_below_10_gb" in report["warnings"]
    assert "projected_object_storage_below_free_tier" in report["failures"]
    assert "projected_m2_requests_below_operational_budget" in report["failures"]


def test_resource_budget_warns_before_reaching_free_storage_limit() -> None:
    report = build_resource_budget_report(
        generated_at=datetime(2026, 9, 13, tzinfo=UTC),
        host={
            "logical_cpus": 2,
            "memory_total_bytes": 12 * 1024**3,
            "memory_available_bytes": 8 * 1024**3,
            "root_total_bytes": 100 * 1024**3,
            "root_used_bytes": 40 * 1024**3,
            "project_bytes": 1024**3,
        },
        containers=[],
        object_storage={
            "object_count": 40,
            "byte_size": 1_600_000_000,
            "m2_evidence_object_count": 30,
            "m2_evidence_bytes": 300_000,
            "complete_parquet_object_count": 5,
            "complete_parquet_bytes": 1_600_000_000,
        },
    )

    assert report["status"] == "warning"
    assert report["failures"] == []
    assert report["warnings"] == ["projected_object_storage_below_10_gb"]
    assert report["checks"]["projected_object_storage_below_free_tier"] is True
