# ADR-021 — Shape-first ETA V0 with explicit unavailability

## Status

Accepted on 2026-09-12.

## Context

ETA requires a trustworthy link between each live vehicle and the active GTFS
network. A production audit showed that the Rio feed provides route, trip and
shape identifiers for almost every operational record, but the exact GTFS trip
identifier is not stable enough to be the primary join.

Two bounded live samples produced the following evidence:

- 2,756 latest vehicles, of which 2,523 had a trip identifier;
- 2,507 vehicles matched an active GTFS route exactly;
- only 1,225 matched an active GTFS trip exactly;
- among 10,389 operational source records with route, trip and shape, 10,282
  matched the active GTFS `route_id + shape_id` pair (98.97%);
- the official `stop_times.txt` contains `shape_dist_traveled`, although the
  first importer version did not retain that optional column.

The source adapter already validated `shape_id`, but discarded it when creating
the canonical vehicle position. Continuing to discard it would weaken both ETA
and future historical replay.

## Decision

1. Preserve nullable `shape_id` in the canonical model, PostGIS, Valkey, public
   API and new Parquet archives. It does not change the position deduplication
   identity.
2. Preserve nullable `shape_dist_traveled` on future GTFS imports.
3. Use a validated active-snapshot `route_id + shape_id` match as the primary
   path association. Treat exact `trip_id` as stronger auxiliary evidence, not
   a prerequisite.
4. Project the vehicle and candidate stops onto the ordered shape, reject
   excessive off-shape distance, and return only stops ahead of the vehicle.
5. Derive ETA V0 from bounded operational speed evidence and geometric distance.
   Scheduled timing may be a fallback only when the active service and stop
   pattern are unambiguous.
6. Every response carries observation age, method and evidence. When any gate
   fails, return a stable unavailability reason instead of a numeric ETA.
7. Do not label ETA V0 as high-confidence. Confidence claims require historical
   replay with MAE and P50/P90 evidence.

Initial unavailability reasons are: stale or invalid GPS, missing shape,
shape absent from the active snapshot, route/shape mismatch, excessive
off-shape distance, ambiguous stop pattern, no upcoming stop, and insufficient
speed evidence.

## Consequences

New realtime and archive rows retain the strongest source link available for
ETA. Existing Parquet objects remain immutable and verifiable; older rows simply
have no `shape_id` evidence. The active GTFS snapshot must be refreshed or
rehydrated before its previously discarded stop-distance values can be used.
The first ETA endpoint will remain unavailable for cases that cannot satisfy the
gates above, even if a visually plausible estimate could be fabricated.
