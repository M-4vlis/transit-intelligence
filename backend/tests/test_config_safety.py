import pytest

from app.core.config import Settings


def test_destructive_retention_is_disabled_by_default() -> None:
    settings = Settings(_env_file=None)
    assert settings.destructive_retention_enabled is False
    assert settings.hot_retention_days == 7


def test_local_archive_cannot_authorize_destructive_retention() -> None:
    settings = Settings(
        _env_file=None,
        archive_storage_kind="local",
        destructive_retention_enabled=True,
    )
    with pytest.raises(ValueError, match="durable external archive"):
        settings.validate_destructive_retention()


def test_external_archive_can_authorize_retention_gate() -> None:
    settings = Settings(
        _env_file=None,
        archive_storage_kind="s3",
        destructive_retention_enabled=True,
    )
    settings.validate_destructive_retention()
    assert settings.retention_is_safe is True


def test_s3_archive_requires_complete_configuration() -> None:
    settings = Settings(_env_file=None, archive_storage_kind="s3")
    with pytest.raises(ValueError, match="missing S3 archive configuration"):
        settings.validate_archive_storage()


def test_s3_archive_accepts_complete_https_configuration() -> None:
    settings = Settings(
        _env_file=None,
        archive_storage_kind="oci-s3",
        archive_s3_endpoint="https://namespace.compat.objectstorage.sa-saopaulo-1.oci.customer-oci.com",
        archive_s3_region="sa-saopaulo-1",
        archive_s3_bucket="transit-history",
        archive_s3_access_key_id="access",
        archive_s3_secret_access_key="secret",
    )
    settings.validate_archive_storage()


def test_unknown_archive_kind_never_authorizes_destructive_retention() -> None:
    settings = Settings(
        _env_file=None,
        archive_storage_kind="mystery-store",
        destructive_retention_enabled=True,
    )
    assert settings.retention_is_safe is False
    with pytest.raises(ValueError, match="unsupported archive storage kind"):
        settings.validate_archive_storage()
    with pytest.raises(ValueError, match="durable external archive"):
        settings.validate_destructive_retention()


def test_gtfs_source_is_separately_allowlisted_and_bounded() -> None:
    settings = Settings(_env_file=None)

    assert settings.gtfs_allowed_source_hosts == {"dados.mobilidade.rio"}
    assert settings.rio_gtfs_url == "https://dados.mobilidade.rio/gtfs/schedule"
    assert settings.gtfs_max_compressed_bytes == 64 * 1024 * 1024
    assert settings.gtfs_max_uncompressed_bytes == 512 * 1024 * 1024


def test_realtime_window_is_bounded_and_uses_conservative_cadence() -> None:
    settings = Settings(_env_file=None)

    assert settings.rio_poll_interval_seconds == 60
    assert settings.rio_realtime_initial_window_seconds == 120
    assert settings.rio_realtime_overlap_seconds == 30
    assert settings.rio_realtime_max_window_seconds == 300
    assert settings.rio_realtime_max_response_bytes == 32 * 1024 * 1024
    assert settings.source_timeout_seconds == 20


def test_realtime_window_rejects_invalid_cross_field_limits() -> None:
    with pytest.raises(ValueError, match="initial realtime window"):
        Settings(
            _env_file=None,
            rio_realtime_initial_window_seconds=301,
            rio_realtime_max_window_seconds=300,
        )

    with pytest.raises(ValueError, match="realtime overlap"):
        Settings(
            _env_file=None,
            rio_realtime_overlap_seconds=300,
            rio_realtime_max_window_seconds=300,
        )
