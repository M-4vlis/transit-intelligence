# ADR-025: Incremental segment/time-band profiles for ETA fallback

## Status

Accepted.

## Context

ETA V0 primarily uses recent speed evidence from the same vehicle and falls
back to the same route and shape. Querying tens of millions of raw GPS rows on
an API request is not safe on the Oracle free-tier host. The first five hot
partitions already represented roughly 38 million rows.

## Decision

- Aggregate only valid speeds between 0.8 and 22.22 m/s.
- Use complete 15-minute windows.
- Define a coarse segment as a 0.0025-degree spatial cell, approximately 250 m
  in Rio de Janeiro.
- Store P25, median, P75 and sample count per route, cell and local time band.
- Refresh the latest hour every 15 minutes in an isolated one-shot container.
- Bound each refresh with a five-minute PostgreSQL statement timeout.
- On an API request, search the current and eight neighboring cells, the local
  time band plus or minus 15 minutes, and at most seven days of profiles.
- Require at least two windows and 50 samples.
- Preserve the evidence hierarchy: same-vehicle recent speed, historical
  segment/time-band profile, then recent route/shape speed.
- Keep all ETA responses at `experimental` confidence.

## Consequences

API queries read a small derived table rather than scanning raw partitions.
The aggregation is idempotent and does not delete or mutate raw GPS history.
Spatial cells are deliberately coarse and may mix nearby parallel roads, so
historical evidence is only a bounded fallback, not a reliability claim.
