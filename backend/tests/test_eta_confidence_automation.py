from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "infra" / "scripts" / "run_eta_confidence_cohort.sh"
SERVICE = (
    ROOT
    / "infra"
    / "systemd"
    / "transit-intelligence-eta-confidence-cohort.service"
)
TIMER = (
    ROOT
    / "infra"
    / "systemd"
    / "transit-intelligence-eta-confidence-cohort.timer"
)
COMPOSE = ROOT / "infra" / "docker-compose.production.yml"
RESTORE_SERVICE = (
    ROOT
    / "infra"
    / "systemd"
    / "transit-intelligence-confidence-evidence-restore.service"
)
RESTORE_TIMER = (
    ROOT
    / "infra"
    / "systemd"
    / "transit-intelligence-confidence-evidence-restore.timer"
)
MONITOR_SCRIPT = ROOT / "infra" / "scripts" / "monitor_eta_confidence_operations.sh"
MONITOR_SERVICE = (
    ROOT / "infra" / "systemd" / "transit-intelligence-eta-confidence-monitor.service"
)
MONITOR_TIMER = (
    ROOT / "infra" / "systemd" / "transit-intelligence-eta-confidence-monitor.timer"
)
READINESS_SCRIPT = ROOT / "infra" / "scripts" / "build_m2_readiness_report.sh"
BUDGET_SERVICE = (
    ROOT / "infra" / "systemd" / "transit-intelligence-m2-resource-budget.service"
)
BUDGET_TIMER = (
    ROOT / "infra" / "systemd" / "transit-intelligence-m2-resource-budget.timer"
)


def test_cohort_script_is_concurrent_safe_and_keeps_audit_artifacts() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    assert "set -euo pipefail" in script
    assert "umask 077" in script
    assert "flock -n" in script
    assert "run --rm -T eta-replay" in script
    assert 'sha256sum "$report"' in script
    assert 'sha256sum "$summary"' in script
    assert "summary-latest.json" in script
    assert 'sha256sum "$calibration"' in script
    assert "calibration-latest.json" in script


def test_cohort_timer_is_persistent_and_runs_across_the_day() -> None:
    timer = TIMER.read_text(encoding="utf-8")

    assert "00,03,06,09,12,15,18,21:35:00 UTC" in timer
    assert "Persistent=true" in timer
    assert "WantedBy=timers.target" in timer


def test_cohort_service_has_low_resource_priority_and_no_privilege_gain() -> None:
    service = SERVICE.read_text(encoding="utf-8")

    assert "User=ubuntu" in service
    assert "Nice=15" in service
    assert "IOSchedulingClass=idle" in service
    assert "CPUWeight=10" in service
    assert "IOWeight=10" in service
    assert "NoNewPrivileges=true" in service


def test_eta_replay_has_explicit_resource_limits() -> None:
    compose = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    replay = compose["services"]["eta-replay"]

    assert replay["mem_limit"] == "768m"
    assert replay["cpus"] == 0.35


def test_confidence_evidence_services_are_bounded_and_have_no_data_access() -> None:
    compose = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    services = compose["services"]
    archive = services["confidence-evidence-archive"]
    restore = services["confidence-evidence-restore-check"]

    assert archive["networks"] == ["egress"]
    assert restore["networks"] == ["egress"]
    assert archive["read_only"] is True
    assert restore["read_only"] is True
    assert archive["cap_drop"] == ["ALL"]
    assert restore["cap_drop"] == ["ALL"]
    assert archive["mem_limit"] == "256m"
    assert restore["mem_limit"] == "256m"
    assert archive["user"] == (
        "${TRANSIT_CONFIDENCE_UID:-1001}:${TRANSIT_CONFIDENCE_GID:-1001}"
    )
    assert ":/evidence" in archive["volumes"][0]


def test_confidence_restore_timer_is_daily_persistent_and_low_priority() -> None:
    timer = RESTORE_TIMER.read_text(encoding="utf-8")
    service = RESTORE_SERVICE.read_text(encoding="utf-8")

    assert "OnCalendar=*-*-* 05:20:00 UTC" in timer
    assert "Persistent=true" in timer
    assert "WantedBy=timers.target" in timer
    assert "User=ubuntu" in service
    assert "Nice=15" in service
    assert "CPUWeight=10" in service
    assert "NoNewPrivileges=true" in service


def test_confidence_monitor_is_frequent_persistent_and_records_failures() -> None:
    script = MONITOR_SCRIPT.read_text(encoding="utf-8")
    service = MONITOR_SERVICE.read_text(encoding="utf-8")
    timer = MONITOR_TIMER.read_text(encoding="utf-8")

    assert "operations-latest.json" in script
    assert "transit-intelligence-eta-confidence-cohort.service" in script
    assert "transit-intelligence-confidence-evidence-restore.service" in script
    assert "transit-intelligence-m2-resource-budget.service" in script
    assert "transit-intelligence-verified-retention.service" in script
    assert "OnCalendar=*:0/30" in timer
    assert "Persistent=true" in timer
    assert "User=ubuntu" in service
    assert "Nice=15" in service
    assert "NoNewPrivileges=true" in service


def test_cohort_builds_and_archives_guarded_readiness_report() -> None:
    cohort = SCRIPT.read_text(encoding="utf-8")
    readiness = READINESS_SCRIPT.read_text(encoding="utf-8")

    assert "monitor_eta_confidence_operations.sh" in cohort
    assert "build_m2_readiness_report.sh" in cohort
    assert cohort.count("run --rm -T confidence-evidence-archive") == 2
    assert "readiness-latest.json" in readiness
    assert 'sha256sum "$report"' in readiness
    assert 'd["promotion_authorized"] is False' in readiness


def test_resource_budget_service_is_bounded_and_scheduled_daily() -> None:
    compose = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    budget = compose["services"]["m2-resource-budget"]
    service = BUDGET_SERVICE.read_text(encoding="utf-8")
    timer = BUDGET_TIMER.read_text(encoding="utf-8")

    assert budget["networks"] == ["egress"]
    assert budget["read_only"] is True
    assert budget["cap_drop"] == ["ALL"]
    assert budget["mem_limit"] == "256m"
    assert budget["cpus"] == 0.2
    assert "OnCalendar=*-*-* 06:20:00 UTC" in timer
    assert "Persistent=true" in timer
    assert "User=ubuntu" in service
    assert "Nice=15" in service
    assert "NoNewPrivileges=true" in service
