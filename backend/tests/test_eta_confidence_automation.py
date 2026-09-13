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
