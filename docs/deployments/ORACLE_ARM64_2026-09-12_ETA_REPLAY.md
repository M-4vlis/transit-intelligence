# Oracle ARM64 — ETA V0 historical replay — 2026-09-12

## Outcome

A read-only evaluator now replays the production ETA against later GPS
observations. It reuses the same vehicle-to-stop matching and ETA code, only
uses evidence available at the historical anchor time, and writes no data.

The first production-sized sample produced enough observed outcomes to measure
the baseline, but not enough accuracy to promote ETA V0 beyond
`experimental`.

## Production baseline

- 50 vehicle anchors from a three-minute window 45 minutes in the past;
- 22 observed arrivals within 75 m of the predicted next stop;
- MAE: 39.358 seconds;
- absolute error P50: 16.069 seconds;
- absolute error P90: 47.448 seconds;
- signed bias: -27.519 seconds, meaning predictions were early on average;
- uncertainty-interval coverage: 27.27%;
- evidence methods: 19 same-vehicle and 3 route/shape fallback predictions;
- matching methods: 5 exact-trip and 17 route/shape-pattern matches;
- exclusions: 15 arrivals not observed, 5 route/shape patterns not found and
  8 vehicles more than 250 m from the matched shape.

The preceding 20-anchor smoke sample also completed successfully with 12
outcomes. Its high P90 confirmed that a larger sample was necessary before
drawing conclusions.

## Safety and deployment evidence

- implementation commits: `b3e481c`, `cb46951`;
- CI run `34715454782` passed all five jobs, including the real PostgreSQL
  integration and the `amd64`/`arm64` PostGIS build;
- the evaluator container has only the internal data network, a read-only
  filesystem, no Linux capabilities and `no-new-privileges`;
- only the one-shot `eta-replay` image was built; no long-running service was
  replaced or restarted;
- the final stack smoke passed database, cache and recent-position checks with
  an observation age of approximately 35 seconds;
- API, PostgreSQL, Valkey, ingestion worker, edge proxy and preview tunnel were
  all running with zero restarts;
- `.env.production` remained mode `600` with SHA-256
  `800e640768673f08f3190719d868fbb8e5df3412508e91307776c4ddd384570a`;
- destructive retention remained disabled.

## Decision

Keep ETA V0 explicitly experimental. The next prediction iteration should use
historical segment/time-band travel times and recalibrate the uncertainty
interval before any reliability claim.
