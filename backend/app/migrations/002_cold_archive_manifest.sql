CREATE TABLE IF NOT EXISTS transit.cold_archive_manifests (
    id bigserial PRIMARY KEY,
    source text NOT NULL,
    archive_day date NOT NULL,
    object_uri text NOT NULL,
    format text NOT NULL CHECK (format IN ('parquet')),
    row_count bigint NOT NULL CHECK (row_count >= 0),
    byte_size bigint NOT NULL CHECK (byte_size >= 0),
    sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    status text NOT NULL CHECK (status IN ('written','verified','failed')),
    written_at timestamptz NOT NULL DEFAULT now(),
    verified_at timestamptz,
    error_detail text,
    UNIQUE (source, archive_day, object_uri)
);

CREATE INDEX IF NOT EXISTS ix_cold_archive_manifest_lookup
    ON transit.cold_archive_manifests (source, archive_day, status);
