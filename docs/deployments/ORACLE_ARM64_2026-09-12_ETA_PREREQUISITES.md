# Oracle ARM64 — M1.3 ETA prerequisites — 2026-09-12

## Outcome

The first ETA prerequisite is live in production. Realtime `shape_id` is now
preserved in the canonical position, PostgreSQL, Valkey, public API and future
Parquet archives. Future GTFS imports also retain the optional
`stop_times.shape_dist_traveled` value.

No ETA is exposed yet and the Android v0.1.2 package was not changed.

## Live feasibility evidence

- 11,121 source records were validated in a bounded two-minute sample;
- 10,623 carried route, trip and shape identifiers;
- in a second sample, 10,282 of 10,389 operational records (98.97%) matched an
  active GTFS `route_id + shape_id` pair;
- only 5,010 of those records matched an exact active `trip_id`, establishing
  shape-first matching as the safer V0 strategy;
- the active GTFS manifest confirms that `stop_times.txt` supplies
  `shape_dist_traveled`.

## Deployment verification

- commit: `0ccee06`;
- CI run: `34698112850` (`success`);
- migration `007_eta_prerequisites.sql`: applied;
- ARM64 production preflight: passed;
- route `O0483AAA0A`: 30 live vehicles, all 30 with `shape_id` in both the local
  API and temporary HTTPS edge;
- PostgreSQL latest route sample persisted `shape_id=bh49`;
- stack smoke: database, cache and recent position passed;
- destructive retention remained disabled and no archive was changed.

## Diagnostic incident

A broad post-deployment count query continued running after its client timed
out and caused one ingestion database timeout. The four matching diagnostic
queries were identified and cancelled without terminating database sessions or
modifying data. The next cycle recovered with 8,101 received records, 7,915
persisted records, 7,767 cache updates and zero rejected records.

This exposed a pre-existing reliability gap: the source cursor currently
advances after a successful fetch, before persistence completes. M1.3 now
requires persistence-aware window acknowledgement so a failed cycle can replay
its full source window.

## Device feedback retained for M1.4

The first usable-device test confirmed startup, realtime data, route search and
local favorites. User-location centering, map gestures, marker identification,
decluttering and route filtering are explicitly deferred to the M1.4 map UX
refinement after ETA V0.
