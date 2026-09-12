# Oracle ARM64 — historical ETA profiles — 2026-09-12

## Outcome

ETA V0 now has a bounded historical fallback based on route, an approximately
250 m spatial cell and a 15-minute local time band. Same-vehicle recent speed
remains the first choice and recent route/shape speed remains the final
fallback. Confidence remains `experimental`.

## Data and runtime cost

- 30-hour initial backfill: 799,498 profiles in approximately 166 seconds;
- first incremental refresh: 26,209 profiles in approximately 5 seconds;
- profiles after refresh: 825,707 rows, 208 MB;
- covered interval: 2026-09-11 13:15 UTC through 2026-09-12 20:15 UTC;
- automated refresh: latest one hour every 15 minutes;
- PostgreSQL statement timeout: five minutes;
- no raw GPS row is changed or deleted.

## Reproducible A/B replay

Three fixed anchors compared the previous algorithm and the candidate over 69
observed arrivals. Results were identical at every anchor, so the fallback
introduced no measured regression:

| Anchor UTC | Outcomes | MAE | P50 | P90 | Coverage |
| --- | ---: | ---: | ---: | ---: | ---: |
| 19:15 | 23 | 35.449 s | 11.533 s | 47.287 s | 26.09% |
| 19:30 | 24 | 119.430 s | 8.717 s | 222.025 s | 37.50% |
| 19:45 | 22 | 39.354 s | 19.243 s | 86.565 s | 31.82% |

Historical evidence replaced one route/shape fallback at 19:30 UTC. It did not
change the aggregate metrics at three-decimal precision. This is expected: 61
of 69 evaluated arrivals already had the preferred same-vehicle evidence.

## Verification

- implementation commits: `238d011`, `9b6e698`, `834a90e`;
- CI runs `34716825271` and `34717355952`: all five jobs passed, including
  real PostgreSQL integration and the `amd64`/`arm64` PostGIS build;
- migration `008_eta_segment_speed_profiles.sql` applied;
- systemd timer active, first run successful, next run scheduled 15 minutes
  later;
- live endpoint returned a matched trip, projection gap of approximately 3.3 m,
  nine same-vehicle samples and three bounded stop ETAs;
- final stack smoke passed database, cache and recent-position checks;
- all six long-running containers were running and healthy where applicable,
  with zero restarts;
- `.env.production` remained mode `600` with SHA-256
  `800e640768673f08f3190719d868fbb8e5df3412508e91307776c4ddd384570a`;
- destructive raw-history retention remained disabled.

## Decision

Keep the historical fallback enabled. It expands evidence coverage without a
measured regression, but it does not yet correct the early-arrival bias or the
poor uncertainty coverage. Those remain explicit gates before any confidence
promotion.
