from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _read_object_storage_bytes(path: Path, maximum_age_seconds: int) -> tuple[int | None, str]:
    try:
        age = datetime.now(UTC).timestamp() - path.stat().st_mtime
        if age > maximum_age_seconds:
            return None, "stale"
        report = json.loads(path.read_text(encoding="utf-8"))
        return int(report["object_storage"]["byte_size"]), "current"
    except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None, "unavailable"


def build_plan(
    *,
    root_used_percent: float,
    object_storage_bytes: int | None,
    object_storage_status: str,
    paused_by_guard: bool,
    warning_percent: float = 80,
    critical_percent: float = 90,
    resume_percent: float = 75,
    object_warning_bytes: int = 15_000_000_000,
    object_hard_guard_bytes: int = 18_000_000_000,
) -> dict[str, Any]:
    if not 0 <= resume_percent < warning_percent < critical_percent <= 100:
        raise ValueError("capacity thresholds must satisfy resume < warning < critical")
    if not 0 < object_warning_bytes < object_hard_guard_bytes:
        raise ValueError("object storage thresholds are invalid")

    object_hard = object_storage_bytes is not None and object_storage_bytes >= object_hard_guard_bytes
    disk_critical = root_used_percent >= critical_percent
    disk_warning = root_used_percent >= warning_percent
    object_warning = object_storage_bytes is not None and object_storage_bytes >= object_warning_bytes

    pause_collector = object_hard or disk_critical
    # Retention archives before dropping. Never start it without a recent
    # storage measurement or after the Object Storage hard guard is reached.
    attempt_verified_retention = disk_warning and object_storage_status == "current" and not object_hard
    resume_collector = (
        paused_by_guard
        and root_used_percent <= resume_percent
        and not object_hard
        and object_storage_status == "current"
    )

    if object_hard:
        reason = "object_storage_hard_guard"
    elif disk_critical:
        reason = "root_filesystem_critical"
    elif resume_collector:
        reason = "capacity_recovered"
    elif paused_by_guard:
        reason = "guard_pause_preserved"
    elif disk_warning:
        reason = "root_filesystem_warning"
    elif object_warning:
        reason = "object_storage_warning"
    elif object_storage_status != "current":
        reason = "object_storage_measurement_unavailable"
    else:
        reason = "within_capacity"

    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "blocked" if pause_collector or paused_by_guard else "passed",
        "reason": reason,
        "measurements": {
            "root_used_percent": round(root_used_percent, 2),
            "object_storage_bytes": object_storage_bytes,
            "object_storage_status": object_storage_status,
        },
        "thresholds": {
            "root_warning_percent": warning_percent,
            "root_critical_percent": critical_percent,
            "root_resume_percent": resume_percent,
            "object_warning_bytes": object_warning_bytes,
            "object_hard_guard_bytes": object_hard_guard_bytes,
        },
        "actions": {
            "pause_collector": pause_collector,
            "attempt_verified_retention": attempt_verified_retention,
            "resume_collector": resume_collector,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root-path", default="/")
    parser.add_argument("--budget-report", type=Path, required=True)
    parser.add_argument("--pause-marker", type=Path, required=True)
    parser.add_argument("--maximum-budget-age-seconds", type=int, default=129_600)
    parser.add_argument("--warning-percent", type=float, default=80)
    parser.add_argument("--critical-percent", type=float, default=90)
    parser.add_argument("--resume-percent", type=float, default=75)
    parser.add_argument("--object-warning-bytes", type=int, default=15_000_000_000)
    parser.add_argument("--object-hard-guard-bytes", type=int, default=18_000_000_000)
    args = parser.parse_args()

    usage = shutil.disk_usage(args.root_path)
    root_used_percent = (usage.used / usage.total) * 100
    object_bytes, object_status = _read_object_storage_bytes(
        args.budget_report, args.maximum_budget_age_seconds
    )
    plan = build_plan(
        root_used_percent=root_used_percent,
        object_storage_bytes=object_bytes,
        object_storage_status=object_status,
        paused_by_guard=args.pause_marker.exists(),
        warning_percent=args.warning_percent,
        critical_percent=args.critical_percent,
        resume_percent=args.resume_percent,
        object_warning_bytes=args.object_warning_bytes,
        object_hard_guard_bytes=args.object_hard_guard_bytes,
    )
    json.dump(plan, fp=sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
