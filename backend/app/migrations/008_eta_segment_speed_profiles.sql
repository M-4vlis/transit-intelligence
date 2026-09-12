CREATE TABLE IF NOT EXISTS transit.eta_segment_speed_profiles (
    window_start timestamptz NOT NULL,
    window_end timestamptz NOT NULL,
    route_id text NOT NULL,
    latitude_cell integer NOT NULL,
    longitude_cell integer NOT NULL,
    local_time_band smallint NOT NULL CHECK (local_time_band BETWEEN 0 AND 95),
    sample_count integer NOT NULL CHECK (sample_count > 0),
    speed_p25_mps real NOT NULL CHECK (speed_p25_mps > 0),
    speed_median_mps real NOT NULL CHECK (speed_median_mps > 0),
    speed_p75_mps real NOT NULL CHECK (speed_p75_mps > 0),
    refreshed_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (window_start, route_id, latitude_cell, longitude_cell),
    CHECK (window_end = window_start + interval '15 minutes'),
    CHECK (speed_p25_mps <= speed_median_mps),
    CHECK (speed_median_mps <= speed_p75_mps)
);

CREATE INDEX IF NOT EXISTS ix_eta_segment_profiles_lookup
    ON transit.eta_segment_speed_profiles (
        route_id,
        latitude_cell,
        longitude_cell,
        window_end DESC
    );
