ALTER TABLE transit.ingestion_runs
    ADD COLUMN IF NOT EXISTS contract_fingerprint text,
    ADD COLUMN IF NOT EXISTS observed_fields jsonb NOT NULL DEFAULT '[]'::jsonb;

CREATE INDEX IF NOT EXISTS ix_ingestion_runs_contract_fingerprint
    ON transit.ingestion_runs (source, contract_fingerprint, finished_at DESC);
