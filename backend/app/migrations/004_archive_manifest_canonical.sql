-- One canonical cold archive per source/day makes archival idempotent and prevents ambiguity
-- during destructive retention checks.
CREATE UNIQUE INDEX IF NOT EXISTS ux_cold_archive_manifest_source_day
    ON transit.cold_archive_manifests (source, archive_day);
