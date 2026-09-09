from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    log_level: str = "INFO"
    infrastructure_enabled: bool = False

    database_url: str = "postgresql://transit_app:local-only-change-me@postgres:5432/transit"
    cache_url: str = "redis://redis:6379/0"

    rio_realtime_url: str = "https://dados.mobilidade.rio/gps/sppo"
    rio_allowed_source_hosts: str = "dados.mobilidade.rio"
    rio_gtfs_url: str = (
        "https://www.arcgis.com/sharing/rest/content/items/"
        "8ffe62ad3b2f42e49814bf941654ea6c/data"
    )
    rio_gtfs_allowed_source_hosts: str = "www.arcgis.com"
    gtfs_max_compressed_bytes: int = 64 * 1024 * 1024
    gtfs_max_uncompressed_bytes: int = 512 * 1024 * 1024
    gtfs_max_members: int = 128
    rio_poll_interval_seconds: float = Field(default=60.0, gt=0)
    rio_realtime_initial_window_seconds: float = Field(default=120.0, gt=0)
    rio_realtime_overlap_seconds: float = Field(default=30.0, ge=0)
    rio_realtime_max_window_seconds: float = Field(default=300.0, gt=0)
    rio_realtime_max_response_bytes: int = Field(default=32 * 1024 * 1024, gt=0)
    source_timeout_seconds: float = Field(default=20.0, gt=0)
    live_position_ttl_seconds: int = 180
    hot_retention_days: int = 2
    archive_batch_size: int = 50_000
    archive_storage_kind: str = "local"
    archive_local_root: str = "/data/archive"
    archive_s3_endpoint: str = ""
    archive_s3_region: str = ""
    archive_s3_bucket: str = ""
    archive_s3_access_key_id: str = ""
    archive_s3_secret_access_key: str = ""
    archive_s3_prefix: str = "transit-history"
    destructive_retention_enabled: bool = False
    worker_metrics_port: int = 9101

    api_docs_enabled: bool = True
    cors_allowed_origins: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def validate_realtime_window(self) -> "Settings":
        if self.rio_realtime_initial_window_seconds > self.rio_realtime_max_window_seconds:
            raise ValueError("initial realtime window cannot exceed its maximum")
        if self.rio_realtime_overlap_seconds >= self.rio_realtime_max_window_seconds:
            raise ValueError("realtime overlap must be smaller than the maximum window")
        return self

    @property
    def allowed_origins(self) -> list[str]:
        return [item.strip() for item in self.cors_allowed_origins.split(",") if item.strip()]

    @property
    def retention_is_safe(self) -> bool:
        """Only recognized external object stores may authorize destructive retention."""
        return self.archive_storage_kind.lower() in {"s3", "oci-s3", "r2"}

    def validate_archive_storage(self) -> None:
        kind = self.archive_storage_kind.lower()
        if kind in {"local", "filesystem"}:
            return
        if kind in {"s3", "oci-s3", "r2"}:
            required = {
                "archive_s3_endpoint": self.archive_s3_endpoint,
                "archive_s3_region": self.archive_s3_region,
                "archive_s3_bucket": self.archive_s3_bucket,
                "archive_s3_access_key_id": self.archive_s3_access_key_id,
                "archive_s3_secret_access_key": self.archive_s3_secret_access_key,
            }
            missing = [name for name, value in required.items() if not value.strip()]
            if missing:
                raise ValueError(f"missing S3 archive configuration: {', '.join(missing)}")
            if not self.archive_s3_endpoint.startswith("https://"):
                raise ValueError("S3 archive endpoint must use HTTPS")
            return
        raise ValueError(f"unsupported archive storage kind: {self.archive_storage_kind}")

    def validate_destructive_retention(self) -> None:
        if self.destructive_retention_enabled and not self.retention_is_safe:
            raise ValueError(
                "destructive retention requires durable external archive storage"
            )

    @property
    def allowed_source_hosts(self) -> set[str]:
        return {
            item.strip().lower()
            for item in self.rio_allowed_source_hosts.split(",")
            if item.strip()
        }

    @property
    def gtfs_allowed_source_hosts(self) -> set[str]:
        return {
            item.strip().lower()
            for item in self.rio_gtfs_allowed_source_hosts.split(",")
            if item.strip()
        }


settings = Settings()
