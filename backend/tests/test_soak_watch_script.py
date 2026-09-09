from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WATCHER = ROOT / "infra" / "scripts" / "soak_watch.sh"
UNIT = ROOT / "infra" / "systemd" / "transit-intelligence-soak-watch.service"


def test_soak_watcher_starts_only_after_a_real_success() -> None:
    text = WATCHER.read_text(encoding="utf-8")
    assert "status = 'success'" in text
    assert "persisted_records > 0" in text
    assert "cached_records > 0" in text
    assert "contract_fingerprint IS NOT NULL" in text
    assert "run_soak_gate.sh" in text


def test_soak_watcher_systemd_unit_is_non_root_and_restartable() -> None:
    text = UNIT.read_text(encoding="utf-8")
    assert "User=ubuntu" in text
    assert "SupplementaryGroups=docker" in text
    assert "Restart=on-failure" in text
    assert "NoNewPrivileges=true" in text
