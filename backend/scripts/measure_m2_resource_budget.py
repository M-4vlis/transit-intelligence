from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.infrastructure.parquet import create_s3_compatible_client

_BYTES_PER_GIB = 1024**3
_FREE_COMPUTE_OCPUS = 2
_FREE_COMPUTE_MEMORY_BYTES = 12 * _BYTES_PER_GIB
_CONSERVATIVE_OBJECT_STORAGE_BYTES = 10 * _BYTES_PER_GIB
_FREE_OBJECT_REQUESTS_PER_MONTH = 50_000
_OPERATIONAL_REQUEST_BUDGET = 30_000
_COHORTS_PER_MONTH = 8 * 30
_NUMBER = re.compile(r"([0-9.]+)\s*([A-Za-z]+)?")


def _parse_bytes(value: str) -> int:
    match = _NUMBER.fullmatch(value.strip())
    if match is None:
        raise ValueError(f"invalid byte quantity: {value}")
    number = float(match.group(1))
    unit = (match.group(2) or "B").lower()
    factors = {
        "b": 1,
        "kb": 1000,
        "mb": 1000**2,
        "gb": 1000**3,
        "kib": 1024,
        "mib": 1024**2,
        "gib": 1024**3,
    }
    return int(number * factors[unit])


def _docker_metrics(path: Path) -> list[dict[str, object]]:
    metrics = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        name = str(item.get("Name", ""))
        if not name.startswith("transit-intelligence-"):
            continue
        memory_used = str(item.get("MemUsage", "0B / 0B")).split("/", 1)[0]
        metrics.append(
            {
                "name": name,
                "cpu_percent": float(str(item.get("CPUPerc", "0")).rstrip("%")),
                "memory_used_bytes": _parse_bytes(memory_used),
                "memory_percent": float(str(item.get("MemPerc", "0")).rstrip("%")),
            }
        )
    return metrics


def _object_storage_metrics(client: Any, *, bucket: str, prefix: str) -> dict[str, int]:
    count = 0
    byte_size = 0
    evidence_count = 0
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for item in page.get("Contents", []):
            count += 1
            byte_size += int(item.get("Size", 0))
            if "/_m2-confidence/evidence/" in str(item.get("Key", "")):
                evidence_count += 1
    return {
        "object_count": count,
        "byte_size": byte_size,
        "m2_evidence_object_count": evidence_count,
    }


def build_resource_budget_report(
    *,
    generated_at: datetime,
    host: dict[str, int],
    containers: list[dict[str, object]],
    object_storage: dict[str, int],
) -> dict[str, object]:
    projected_new_evidence = 4 * _COHORTS_PER_MONTH
    average_evidence_size = (
        object_storage["byte_size"] // max(object_storage["object_count"], 1)
    )
    projected_manifest_overhead = 300 * 1024**2
    projected_storage_bytes = (
        object_storage["byte_size"]
        + projected_new_evidence * average_evidence_size
        + projected_manifest_overhead
    )
    archive_requests = 24 * _COHORTS_PER_MONTH
    restore_requests = 30 * (
        object_storage["m2_evidence_object_count"] + projected_new_evidence // 2 + 2
    )
    projected_m2_requests = archive_requests + restore_requests
    cpu_peak = round(sum(float(item["cpu_percent"]) for item in containers), 3)
    memory_used = sum(int(item["memory_used_bytes"]) for item in containers)
    checks = {
        "compute_shape_within_always_free": host["logical_cpus"] <= _FREE_COMPUTE_OCPUS
        and host["memory_total_bytes"] <= _FREE_COMPUTE_MEMORY_BYTES,
        "host_memory_has_2_gib_headroom": host["memory_available_bytes"] >= 2 * _BYTES_PER_GIB,
        "root_filesystem_below_80_percent": host["root_used_bytes"]
        <= host["root_total_bytes"] * 0.8,
        "project_files_below_10_gib": host["project_bytes"] <= 10 * _BYTES_PER_GIB,
        "projected_object_storage_below_10_gib": projected_storage_bytes
        <= _CONSERVATIVE_OBJECT_STORAGE_BYTES,
        "projected_m2_requests_below_operational_budget": projected_m2_requests
        <= _OPERATIONAL_REQUEST_BUDGET,
        "projected_m2_requests_below_free_tier": projected_m2_requests
        <= _FREE_OBJECT_REQUESTS_PER_MONTH,
        "instant_container_cpu_below_150_percent": cpu_peak < 150,
        "container_memory_below_8_gib": memory_used < 8 * _BYTES_PER_GIB,
    }
    failures = [name for name, passed in checks.items() if not passed]
    return {
        "schema_version": 1,
        "generated_at": generated_at.astimezone(UTC).isoformat(),
        "status": "passed" if not failures else "failed",
        "failures": failures,
        "checks": checks,
        "host": host,
        "containers": {
            "observed": containers,
            "instant_cpu_percent_sum": cpu_peak,
            "memory_used_bytes_sum": memory_used,
        },
        "object_storage": {
            **object_storage,
            "projected_bytes_after_30_days": projected_storage_bytes,
            "conservative_storage_limit_bytes": _CONSERVATIVE_OBJECT_STORAGE_BYTES,
            "projected_m2_api_requests_per_month": projected_m2_requests,
            "operational_request_budget": _OPERATIONAL_REQUEST_BUDGET,
            "free_tier_request_limit": _FREE_OBJECT_REQUESTS_PER_MONTH,
            "projection_assumptions": {
                "cohorts_per_month": _COHORTS_PER_MONTH,
                "new_evidence_objects_per_cohort": 4,
                "archive_requests_per_cohort": 24,
                "daily_full_restore_checks": 30,
                "manifest_storage_reserve_bytes": projected_manifest_overhead,
            },
        },
        "limits": {
            "always_free_compute_ocpus": _FREE_COMPUTE_OCPUS,
            "always_free_compute_memory_bytes": _FREE_COMPUTE_MEMORY_BYTES,
            "object_storage_policy": "10 GiB conservative cap; OCI documents 20 GB combined Always Free",
            "tenancy_wide_usage_not_observed": True,
        },
    }


def main() -> None:
    settings.validate_archive_storage()
    stats_path = Path(os.environ.get("M2_DOCKER_STATS_PATH", "/evidence/.docker-stats.jsonl"))
    host = {
        name: int(os.environ[f"M2_{name.upper()}"])
        for name in (
            "logical_cpus",
            "memory_total_bytes",
            "memory_available_bytes",
            "root_total_bytes",
            "root_used_bytes",
            "project_bytes",
        )
    }
    client = create_s3_compatible_client(
        endpoint_url=settings.archive_s3_endpoint,
        region_name=settings.archive_s3_region,
        access_key_id=settings.archive_s3_access_key_id,
        secret_access_key=settings.archive_s3_secret_access_key,
    )
    report = build_resource_budget_report(
        generated_at=datetime.now(UTC),
        host=host,
        containers=_docker_metrics(stats_path),
        object_storage=_object_storage_metrics(
            client,
            bucket=settings.archive_s3_bucket,
            prefix=settings.archive_s3_prefix.strip("/") + "/",
        ),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    raise SystemExit(0 if report["status"] == "passed" else 1)


if __name__ == "__main__":
    main()
