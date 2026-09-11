CREATE TABLE IF NOT EXISTS transit.gtfs_snapshots (
    snapshot_id text PRIMARY KEY CHECK (snapshot_id ~ '^[0-9a-f]{64}$'),
    source_id text NOT NULL,
    source_url text NOT NULL,
    fetched_at timestamptz NOT NULL,
    imported_at timestamptz NOT NULL DEFAULT now(),
    status text NOT NULL CHECK (status IN ('importing','ready','active','superseded')),
    manifest jsonb NOT NULL,
    row_counts jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_gtfs_one_active_snapshot
    ON transit.gtfs_snapshots ((status = 'active'))
    WHERE status = 'active';

CREATE TABLE IF NOT EXISTS transit.gtfs_agencies (
    snapshot_id text NOT NULL REFERENCES transit.gtfs_snapshots(snapshot_id) ON DELETE CASCADE,
    agency_id text NOT NULL,
    agency_name text NOT NULL,
    agency_url text,
    agency_timezone text,
    agency_lang text,
    agency_phone text,
    PRIMARY KEY (snapshot_id, agency_id)
);

CREATE TABLE IF NOT EXISTS transit.gtfs_routes (
    snapshot_id text NOT NULL REFERENCES transit.gtfs_snapshots(snapshot_id) ON DELETE CASCADE,
    route_id text NOT NULL,
    agency_id text,
    route_short_name text,
    route_long_name text,
    route_desc text,
    route_type integer NOT NULL,
    route_color text,
    route_text_color text,
    PRIMARY KEY (snapshot_id, route_id)
);

CREATE INDEX IF NOT EXISTS ix_gtfs_routes_search
    ON transit.gtfs_routes (snapshot_id, lower(route_short_name), lower(route_long_name));

CREATE TABLE IF NOT EXISTS transit.gtfs_stops (
    snapshot_id text NOT NULL REFERENCES transit.gtfs_snapshots(snapshot_id) ON DELETE CASCADE,
    stop_id text NOT NULL,
    stop_code text,
    stop_name text NOT NULL,
    stop_desc text,
    stop_lat double precision NOT NULL CHECK (stop_lat BETWEEN -90 AND 90),
    stop_lon double precision NOT NULL CHECK (stop_lon BETWEEN -180 AND 180),
    zone_id text,
    location_type integer,
    parent_station text,
    wheelchair_boarding integer,
    location geography(Point, 4326) GENERATED ALWAYS AS (
        ST_SetSRID(ST_MakePoint(stop_lon, stop_lat), 4326)::geography
    ) STORED,
    PRIMARY KEY (snapshot_id, stop_id)
);

CREATE INDEX IF NOT EXISTS ix_gtfs_stops_location
    ON transit.gtfs_stops USING GIST (location);
CREATE INDEX IF NOT EXISTS ix_gtfs_stops_name
    ON transit.gtfs_stops (snapshot_id, lower(stop_name));

CREATE TABLE IF NOT EXISTS transit.gtfs_trips (
    snapshot_id text NOT NULL REFERENCES transit.gtfs_snapshots(snapshot_id) ON DELETE CASCADE,
    trip_id text NOT NULL,
    route_id text NOT NULL,
    service_id text NOT NULL,
    trip_headsign text,
    direction_id integer,
    block_id text,
    shape_id text,
    wheelchair_accessible integer,
    PRIMARY KEY (snapshot_id, trip_id)
);

CREATE INDEX IF NOT EXISTS ix_gtfs_trips_route
    ON transit.gtfs_trips (snapshot_id, route_id);
CREATE INDEX IF NOT EXISTS ix_gtfs_trips_shape
    ON transit.gtfs_trips (snapshot_id, shape_id);

CREATE TABLE IF NOT EXISTS transit.gtfs_stop_times (
    snapshot_id text NOT NULL REFERENCES transit.gtfs_snapshots(snapshot_id) ON DELETE CASCADE,
    trip_id text NOT NULL,
    stop_sequence integer NOT NULL CHECK (stop_sequence >= 0),
    arrival_seconds integer,
    departure_seconds integer,
    stop_id text NOT NULL,
    stop_headsign text,
    pickup_type integer,
    drop_off_type integer,
    timepoint integer,
    PRIMARY KEY (snapshot_id, trip_id, stop_sequence)
);

CREATE INDEX IF NOT EXISTS ix_gtfs_stop_times_stop
    ON transit.gtfs_stop_times (snapshot_id, stop_id, departure_seconds);

CREATE TABLE IF NOT EXISTS transit.gtfs_calendars (
    snapshot_id text NOT NULL REFERENCES transit.gtfs_snapshots(snapshot_id) ON DELETE CASCADE,
    service_id text NOT NULL,
    monday boolean NOT NULL,
    tuesday boolean NOT NULL,
    wednesday boolean NOT NULL,
    thursday boolean NOT NULL,
    friday boolean NOT NULL,
    saturday boolean NOT NULL,
    sunday boolean NOT NULL,
    start_date date NOT NULL,
    end_date date NOT NULL,
    PRIMARY KEY (snapshot_id, service_id)
);

CREATE TABLE IF NOT EXISTS transit.gtfs_calendar_dates (
    snapshot_id text NOT NULL REFERENCES transit.gtfs_snapshots(snapshot_id) ON DELETE CASCADE,
    service_id text NOT NULL,
    service_date date NOT NULL,
    exception_type integer NOT NULL CHECK (exception_type IN (1,2)),
    PRIMARY KEY (snapshot_id, service_id, service_date)
);

CREATE TABLE IF NOT EXISTS transit.gtfs_shapes (
    snapshot_id text NOT NULL REFERENCES transit.gtfs_snapshots(snapshot_id) ON DELETE CASCADE,
    shape_id text NOT NULL,
    shape_pt_sequence integer NOT NULL CHECK (shape_pt_sequence >= 0),
    shape_pt_lat double precision NOT NULL CHECK (shape_pt_lat BETWEEN -90 AND 90),
    shape_pt_lon double precision NOT NULL CHECK (shape_pt_lon BETWEEN -180 AND 180),
    shape_dist_traveled double precision,
    location geometry(Point, 4326) GENERATED ALWAYS AS (
        ST_SetSRID(ST_MakePoint(shape_pt_lon, shape_pt_lat), 4326)
    ) STORED,
    PRIMARY KEY (snapshot_id, shape_id, shape_pt_sequence)
);

CREATE INDEX IF NOT EXISTS ix_gtfs_shapes_lookup
    ON transit.gtfs_shapes (snapshot_id, shape_id, shape_pt_sequence);
