from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

from scripts.check_eta_confidence_operations import build_operations_report


def _write(directory: Path, name: str, payload: str) -> None:
    path = directory / name
    path.write_text(payload, encoding="utf-8")
    digest = sha256(path.read_bytes()).hexdigest()
    with (directory / "SHA256SUMS").open("a", encoding="utf-8") as handle:
        handle.write(f"{digest}  {path}\n")


def _fixture(directory: Path, now: datetime) -> None:
    stamp = (now - timedelta(hours=1)).strftime("%Y%m%dT%H%M%SZ")
    cohort_name = f"cohort-{stamp}.json"
    summary_name = f"summary-{stamp}.json"
    calibration_name = f"calibration-{stamp}.json"
    cohort = (
        '{"evaluation_schema_version":2,'
        '"shadow_confidence_contract_version":"m2-shadow-v1",'
        '"candidate_confidence":{"bands":{"high":'
        '{"outcome_count":10,"mae_seconds":30,"interval_coverage":0.8}}}}'
    )
    _write(directory, cohort_name, cohort)
    _write(directory, summary_name, "{}")
    _write(directory, calibration_name, "{}")
    (directory / "summary-latest.json").write_text("{}", encoding="utf-8")
    (directory / "calibration-latest.json").write_text("{}", encoding="utf-8")
    files = {
        path.name: {
            "sha256": sha256(path.read_bytes()).hexdigest(),
            "byte_size": path.stat().st_size,
        }
        for path in directory.glob("*.json")
        if not path.is_symlink()
    }
    (directory / ".object-storage-state.json").write_text(
        '{"schema_version":1,"files":' + __import__("json").dumps(files) + "}",
        encoding="utf-8",
    )


def test_operations_report_passes_complete_fresh_evidence(tmp_path: Path) -> None:
    now = datetime(2026, 9, 13, 15, tzinfo=UTC)
    _fixture(tmp_path, now)

    report = build_operations_report(
        directory=tmp_path,
        now=now,
        maximum_cohort_age_hours=5,
        service_results={
            "cohort": ("success", 0),
            "restore": ("success", 0),
            "resource_budget": ("success", 0),
        },
    )

    assert report["status"] == "passed"
    assert report["checksums"]["verified_file_count"] == 3
    assert report["object_storage_archive"]["missing_files"] == []
    assert report["drift"]["status"] == "insufficient_history"


def test_operations_report_fails_overdue_tampered_and_unarchived(tmp_path: Path) -> None:
    now = datetime(2026, 9, 13, 15, tzinfo=UTC)
    _fixture(tmp_path, now - timedelta(hours=8))
    summary = next(tmp_path.glob("summary-*.json"))
    summary.write_text('{"changed":true}', encoding="utf-8")

    report = build_operations_report(
        directory=tmp_path,
        now=now,
        maximum_cohort_age_hours=5,
        service_results={
            "cohort": ("exit-code", 1),
            "restore": ("success", 0),
            "resource_budget": ("success", 0),
        },
    )

    assert report["status"] == "failed"
    assert "cohort_overdue" in report["failures"]
    assert "checksum_integrity_failed" in report["failures"]
    assert "archived_evidence_changed" in report["failures"]
    assert "service_failed:cohort" in report["failures"]
