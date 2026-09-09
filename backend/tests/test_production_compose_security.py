from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
COMPOSE_PATH = ROOT / "infra" / "docker-compose.production.yml"
POSTGRES_DOCKERFILE = ROOT / "infra" / "postgres" / "Dockerfile"
APP_DOCKERFILE = ROOT / "backend" / "Dockerfile"


def _compose() -> dict:
    return yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))


def test_data_services_are_not_published_to_host():
    services = _compose()["services"]
    assert "ports" not in services["postgres"]
    assert "ports" not in services["redis"]


def test_api_and_metrics_bind_only_to_loopback():
    services = _compose()["services"]
    assert services["api"]["ports"] == [
        "127.0.0.1:${TRANSIT_API_HOST_PORT:-18000}:8000"
    ]
    assert services["rio-ingestion"]["ports"] == ["127.0.0.1:9101:9101"]


def test_internal_data_network_and_valkey_auth_are_required():
    compose = _compose()
    assert compose["networks"]["data"]["internal"] is True
    redis_command = " ".join(str(item) for item in compose["services"]["redis"]["command"])
    assert "--requirepass" in redis_command
    assert "CACHE_PASSWORD" in redis_command


def test_destructive_retention_defaults_to_false():
    text = COMPOSE_PATH.read_text(encoding="utf-8")
    assert "DESTRUCTIVE_RETENTION_ENABLED: ${DESTRUCTIVE_RETENTION_ENABLED:-false}" in text


def test_database_image_uses_official_multiarch_postgres_base():
    dockerfile = POSTGRES_DOCKERFILE.read_text(encoding="utf-8")
    assert "FROM postgres:17.11-trixie" in dockerfile
    assert "postgresql-17-postgis-3" in dockerfile
    assert "imresamu" not in dockerfile.lower()
    assert "postgis/postgis" not in dockerfile.lower()


def test_operational_scripts_can_import_application_package():
    dockerfile = APP_DOCKERFILE.read_text(encoding="utf-8")
    assert "PYTHONPATH=/app" in dockerfile


def test_archive_spool_is_owned_by_non_root_runtime_user():
    dockerfile = APP_DOCKERFILE.read_text(encoding="utf-8")
    assert "install -d -o 65532 -g 65532 /data/archive" in dockerfile
    assert "USER 65532:65532" in dockerfile


def test_restore_check_uses_cleanup_backed_archive_volume_for_large_objects():
    service = _compose()["services"]["archive-restore-check"]
    assert service["environment"]["TMPDIR"] == "/data/archive"
    assert "archive_data:/data/archive" in service["volumes"]


def test_retention_preflight_is_non_destructive_and_hardened():
    service = _compose()["services"]["retention-preflight"]
    assert service["command"] == ["python", "scripts/retention_preflight.py"]
    assert service["read_only"] is True
    assert service["restart"] == "no"
    assert service["cap_drop"] == ["ALL"]
    assert "DESTRUCTIVE_RETENTION_ENABLED" not in service["environment"]
