CREATE EXTENSION IF NOT EXISTS postgis;
CREATE SCHEMA IF NOT EXISTS transit;

CREATE TABLE IF NOT EXISTS transit.vehicle_positions (
    ingest_key text NOT NULL,
    agency_id text NOT NULL,
    vehicle_id text NOT NULL,
    route_id text NOT NULL,
    trip_id text,
    latitude double precision NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    longitude double precision NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    speed_mps real CHECK (speed_mps IS NULL OR speed_mps >= 0),
    bearing_deg real CHECK (bearing_deg IS NULL OR (bearing_deg >= 0 AND bearing_deg < 360)),
    observed_at timestamptz NOT NULL,
    received_at timestamptz NOT NULL,
    source text NOT NULL,
    quality_status text NOT NULL CHECK (quality_status IN ('good','degraded','stale','invalid')),
    quality_score real NOT NULL CHECK (quality_score BETWEEN 0 AND 1),
    location geography(Point, 4326) NOT NULL,
    PRIMARY KEY (ingest_key, observed_at)
) PARTITION BY RANGE (observed_at);

CREATE INDEX IF NOT EXISTS ix_vehicle_positions_route_time
    ON transit.vehicle_positions (route_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS ix_vehicle_positions_vehicle_time
    ON transit.vehicle_positions (agency_id, vehicle_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS ix_vehicle_positions_location
    ON transit.vehicle_positions USING GIST (location);
CREATE INDEX IF NOT EXISTS ix_vehicle_positions_observed_brin
    ON transit.vehicle_positions USING BRIN (observed_at);

CREATE OR REPLACE FUNCTION transit.ensure_vehicle_position_partition(p_day date)
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
    part_name text := 'vehicle_positions_' || to_char(p_day, 'YYYYMMDD');
    start_ts timestamptz := (p_day::timestamp AT TIME ZONE 'UTC');
    end_ts timestamptz := ((p_day + 1)::timestamp AT TIME ZONE 'UTC');
BEGIN
    PERFORM pg_advisory_xact_lock(hashtext(part_name));
    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS transit.%I PARTITION OF transit.vehicle_positions FOR VALUES FROM (%L) TO (%L)',
        part_name, start_ts, end_ts
    );
END;
$$;

CREATE TABLE IF NOT EXISTS transit.source_quarantine (
    id bigserial PRIMARY KEY,
    source text NOT NULL,
    payload_hash text NOT NULL,
    reason_code text NOT NULL,
    detail text NOT NULL,
    raw_payload jsonb,
    first_seen_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz NOT NULL DEFAULT now(),
    occurrence_count bigint NOT NULL DEFAULT 1,
    UNIQUE (source, payload_hash, reason_code)
);

CREATE INDEX IF NOT EXISTS ix_source_quarantine_last_seen
    ON transit.source_quarantine (last_seen_at DESC);

CREATE TABLE IF NOT EXISTS transit.ingestion_runs (
    id bigserial PRIMARY KEY,
    source text NOT NULL,
    status text NOT NULL CHECK (status IN ('success','failure')),
    started_at timestamptz NOT NULL,
    finished_at timestamptz NOT NULL,
    received_records integer NOT NULL,
    rejected_records integer NOT NULL,
    deduplicated_records integer NOT NULL,
    persisted_records integer NOT NULL,
    cached_records integer NOT NULL,
    quality_counts jsonb NOT NULL DEFAULT '{}'::jsonb,
    error_type text,
    error_detail text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_ingestion_runs_source_finished
    ON transit.ingestion_runs (source, finished_at DESC);
