from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "infra" / "scripts" / "run_verified_retention_cycle.sh"
SERVICE = ROOT / "infra" / "systemd" / "transit-intelligence-verified-retention.service"
TIMER = ROOT / "infra" / "systemd" / "transit-intelligence-verified-retention.timer"
COMPOSE = ROOT / "infra" / "docker-compose.production.yml"


def test_verified_retention_cycle_fails_closed_before_apply() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "HOT_RETENTION_DAYS=7" in text
    assert "DESTRUCTIVE_RETENTION_ENABLED=true" in text
    assert text.index("stage=archive") < text.index("stage=independent_restore")
    assert text.index("stage=independent_restore") < text.index("stage=retention_preflight")
    assert text.index("protected_days") < text.index("stage=retention_apply")
    assert "python3 -" in text
    assert "run -T --rm retention" in text
    assert "seq 8 -1 1" in text
    assert "archive_days" in text


def test_verified_retention_timer_is_daily_low_priority_and_serialized() -> None:
    service = SERVICE.read_text(encoding="utf-8")
    timer = TIMER.read_text(encoding="utf-8")

    assert "User=ubuntu" in service
    assert "/usr/bin/flock --nonblock" in service
    assert "Nice=15" in service
    assert "IOSchedulingClass=idle" in service
    assert "OnCalendar=*-*-* 03:10:00 UTC" in timer
    assert "Persistent=true" in timer


def test_production_maintenance_jobs_have_resource_limits() -> None:
    services = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))["services"]

    assert services["archive-day"]["mem_limit"] == "2g"
    assert services["archive-day"]["cpus"] == 0.5
    assert services["retention"]["mem_limit"] == "512m"
    assert services["retention-preflight"]["mem_limit"] == "512m"
    assert services["archive-restore-check"]["mem_limit"] == "768m"
