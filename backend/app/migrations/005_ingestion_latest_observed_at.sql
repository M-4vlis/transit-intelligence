ALTER TABLE transit.ingestion_runs
    ADD COLUMN IF NOT EXISTS latest_observed_at timestamptz;

CREATE INDEX IF NOT EXISTS ix_ingestion_runs_latest_observed_at
    ON transit.ingestion_runs (source, latest_observed_at DESC)
    WHERE status = 'success' AND latest_observed_at IS NOT NULL;
