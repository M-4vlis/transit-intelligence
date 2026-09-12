# ADR-024: Bounded experimental ETA V0

## Status

Accepted — 2026-09-12.

## Context

The active Rio GTFS uses `shape_dist_traveled` as metres: across 20 live
shapes, the ratio between GTFS distance and PostGIS geodesic length ranged
from 0.9991 to 1.0014. Recent GPS speed is available but includes stopped
vehicles and outliers. No replay-calibrated segment model exists yet.

## Decision

- Estimate geometric travel time from remaining shape distance and recent GPS
  speed percentiles.
- Prefer at least three valid speed samples from the same vehicle over the
  previous five minutes.
- Fall back to at least 20 valid samples from the same route and shape over the
  previous ten minutes.
- Accept speed evidence only from 0.8 through 22.22 metres per second and from
  non-invalid observations.
- Use P50 speed for the point estimate, P75 for the lower time bound and P25
  for the upper time bound.
- Subtract observation age from the remaining duration and also return the
  absolute estimated arrival timestamp.
- Refuse ETA when the position is older than 90 seconds, speed evidence is
  insufficient, or a stop is more than 20 kilometres ahead.
- Mark every result `experimental` until historical replay establishes error
  and confidence thresholds.

## Consequences

ETA V0 is useful for testing the complete data path while remaining explicit
about uncertainty. It must not be marketed or rendered as a reliable arrival
promise until replay MAE and P50/P90 error gates pass.
