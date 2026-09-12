ALTER TABLE transit.vehicle_positions
    ADD COLUMN IF NOT EXISTS shape_id text;

ALTER TABLE transit.gtfs_stop_times
    ADD COLUMN IF NOT EXISTS shape_dist_traveled double precision;
