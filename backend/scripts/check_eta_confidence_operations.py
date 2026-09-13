from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

_COHORT_NAME = re.compile(r"^cohort-(\d{8}T\d{6}Z)\.json$")
_IMMUTABLE_PREFIXES = ("cohort-", "summary-", "calibration-")
_CURRENT_EVALUATION_SCHEMA = 2
_SHADOW_CONTRACT_VERSION = "m2-shadow-v1"


def _digest(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _cohort_time(path: Path) -> datetime | None:
    match = _COHORT_NAME.fullmatch(path.name)
    if match is None:
        return None
    return datetime.strptime(match.group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)


def _weighted_metric(reports: list[dict[str, Any]], metric: str) -> float | None:
    total = 0.0
    count = 0
    for report in reports:
        candidate = report.get("candidate_confidence", {})
        for band in candidate.get("bands", {}).values():
            outcomes = int(band.get("outcome_count") or 0)
            value = band.get(metric)
            if outcomes and value is not None:
                total += outcomes * float(value)
                count += outcomes
    return round(total / count, 3) if count else None


def _drift(reports: list[dict[str, Any]]) -> dict[str, object]:
    eligible = [
        report
        for report in reports
        if report.get("evaluation_schema_version") == _CURRENT_EVALUATION_SCHEMA
    ]
    if len(eligible) < 6:
        return {
            "status": "insufficient_history",
            "eligible_cohort_count": len(eligible),
            "minimum_cohort_count": 6,
        }
    previous = eligible[-6:-3]
    recent = eligible[-3:]
    previous_mae = _weighted_metric(previous, "mae_seconds")
    recent_mae = _weighted_metric(recent, "mae_seconds")
    previous_coverage = _weighted_metric(previous, "interval_coverage")
    recent_coverage = _weighted_metric(recent, "interval_coverage")
    mae_increase = (
        round(recent_mae - previous_mae, 3)
        if recent_mae is not None and previous_mae is not None
        else None
    )
    coverage_drop = (
        round(previous_coverage - recent_coverage, 4)
        if recent_coverage is not None and previous_coverage is not None
        else None
    )
    degraded = bool(
        (mae_increase is not None and mae_increase > 60 and recent_mae > previous_mae * 1.5)
        or (coverage_drop is not None and coverage_drop > 0.15)
    )
    return {
        "status": "degraded" if degraded else "stable",
        "eligible_cohort_count": len(eligible),
        "comparison": "latest_3_vs_previous_3",
        "previous_mae_seconds": previous_mae,
        "recent_mae_seconds": recent_mae,
        "mae_increase_seconds": mae_increase,
        "previous_interval_coverage": previous_coverage,
        "recent_interval_coverage": recent_coverage,
        "interval_coverage_drop": coverage_drop,
    }


def build_operations_report(
    *,
    directory: Path,
    now: datetime,
    maximum_cohort_age_hours: float,
    service_results: dict[str, tuple[str, int]],
) -> dict[str, object]:
    now = now.astimezone(UTC)
    failures: list[str] = []
    warnings: list[str] = []
    immutable = sorted(
        path
        for path in directory.iterdir()
        if path.is_file()
        and not path.is_symlink()
        and not path.name.endswith("-latest.json")
        and path.name.startswith(_IMMUTABLE_PREFIXES)
        and path.suffix == ".json"
    )
    cohorts = sorted(
        ((stamp, path) for path in immutable if (stamp := _cohort_time(path))),
        key=lambda item: item[0],
    )
    latest_time, latest_path = cohorts[-1] if cohorts else (None, None)
    age_hours = (
        round((now - latest_time).total_seconds() / 3600, 3) if latest_time else None
    )
    if latest_time is None:
        failures.append("no_automated_cohort")
    elif age_hours is not None and age_hours > maximum_cohort_age_hours:
        failures.append("cohort_overdue")

    checksum_path = directory / "SHA256SUMS"
    checksum_entries: dict[str, str] = {}
    checksum_errors: list[str] = []
    if not checksum_path.is_file():
        failures.append("missing_sha256sums")
    else:
        for line in checksum_path.read_text(encoding="utf-8").splitlines():
            parts = line.split(maxsplit=1)
            if len(parts) != 2:
                checksum_errors.append("invalid_line")
                continue
            digest, recorded = parts
            name = Path(recorded.lstrip("* ")).name
            previous = checksum_entries.get(name)
            if previous is not None and previous != digest:
                checksum_errors.append(f"conflicting:{name}")
            checksum_entries[name] = digest
        for path in immutable:
            if checksum_entries.get(path.name) != _digest(path):
                checksum_errors.append(f"mismatch:{path.name}")
        if checksum_errors:
            failures.append("checksum_integrity_failed")

    link_status: dict[str, str] = {}
    for name in ("summary-latest.json", "calibration-latest.json"):
        link = directory / name
        if not link.is_file() or (link.is_symlink() and not link.resolve().is_file()):
            link_status[name] = "invalid"
            failures.append(f"invalid_link:{name}")
        else:
            link_status[name] = link.resolve().name if link.is_symlink() else "regular_file"

    state_path = directory / ".object-storage-state.json"
    archived_files: dict[str, Any] = {}
    if state_path.is_file():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if state.get("schema_version") == 1 and isinstance(state.get("files"), dict):
            archived_files = state["files"]
        else:
            failures.append("invalid_archive_state")
    else:
        failures.append("missing_archive_state")
    missing_archive = [path.name for path in immutable if path.name not in archived_files]
    changed_archive = [
        path.name
        for path in immutable
        if path.name in archived_files
        and (
            archived_files[path.name].get("sha256") != _digest(path)
            or archived_files[path.name].get("byte_size") != path.stat().st_size
        )
    ]
    if missing_archive:
        failures.append("unarchived_evidence")
    if changed_archive:
        failures.append("archived_evidence_changed")

    reports: list[dict[str, Any]] = []
    for _, path in cohorts:
        try:
            reports.append(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            failures.append(f"invalid_cohort:{path.name}")
    latest_report = reports[-1] if reports else {}
    if latest_report.get("evaluation_schema_version") != _CURRENT_EVALUATION_SCHEMA:
        warnings.append("latest_cohort_uses_legacy_evaluation_schema")
    if latest_report.get("shadow_confidence_contract_version") != _SHADOW_CONTRACT_VERSION:
        warnings.append("latest_cohort_precedes_shadow_contract")
    drift = _drift(reports)
    if drift["status"] == "degraded":
        failures.append("confidence_drift_detected")

    service_report = {}
    for name, (result, exit_status) in service_results.items():
        healthy = result in {"success", ""} and exit_status == 0
        service_report[name] = {
            "result": result or "unknown",
            "exit_status": exit_status,
            "healthy": healthy,
        }
        if not healthy:
            failures.append(f"service_failed:{name}")

    return {
        "schema_version": 1,
        "generated_at": now.isoformat(),
        "status": "failed" if failures else "passed_with_warnings" if warnings else "passed",
        "failures": sorted(set(failures)),
        "warnings": sorted(set(warnings)),
        "cohort_freshness": {
            "latest": latest_path.name if latest_path else None,
            "age_hours": age_hours,
            "maximum_age_hours": maximum_cohort_age_hours,
        },
        "checksums": {
            "immutable_file_count": len(immutable),
            "verified_file_count": len(immutable) - len(checksum_errors),
            "errors": checksum_errors,
        },
        "latest_links": link_status,
        "object_storage_archive": {
            "tracked_file_count": len(archived_files),
            "missing_files": missing_archive,
            "changed_files": changed_archive,
        },
        "drift": drift,
        "services": service_report,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check M2 confidence operations")
    parser.add_argument("--reports-dir", type=Path, required=True)
    parser.add_argument("--maximum-cohort-age-hours", type=float, default=5)
    parser.add_argument("--cohort-service-result", default="unknown")
    parser.add_argument("--cohort-service-exit-status", type=int, default=0)
    parser.add_argument("--restore-service-result", default="unknown")
    parser.add_argument("--restore-service-exit-status", type=int, default=0)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report = build_operations_report(
        directory=args.reports_dir,
        now=datetime.now(UTC),
        maximum_cohort_age_hours=args.maximum_cohort_age_hours,
        service_results={
            "cohort": (
                args.cohort_service_result,
                args.cohort_service_exit_status,
            ),
            "restore": (
                args.restore_service_result,
                args.restore_service_exit_status,
            ),
        },
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    raise SystemExit(0 if report["status"] != "failed" else 1)


if __name__ == "__main__":
    main()
