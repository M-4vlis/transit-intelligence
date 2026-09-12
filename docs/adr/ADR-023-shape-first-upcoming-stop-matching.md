# ADR-023: Shape-first upcoming-stop matching

## Status

Accepted — 2026-09-12.

## Context

Realtime route and shape identifiers match the active GTFS catalog much more
often than realtime trip identifiers. Upcoming-stop matching must therefore
remain useful without pretending that a fallback trip is an exact operational
trip.

## Decision

- Prefer the realtime trip only when it belongs to the same active GTFS route
  and shape.
- Otherwise select a deterministic representative stop pattern from the same
  route and shape and label the result `route_shape_pattern`.
- Project the vehicle onto the nearest non-degenerate shape segment and
  interpolate the official `shape_dist_traveled` values at both ends.
- Reject a match when the vehicle is more than 250 metres from the shape.
- Return the projection distance, match method, matched trip and observation
  timestamp with the upcoming stops.
- Return an explicit unavailability reason for missing shapes, absent catalog
  matches, failed projection, off-shape vehicles and exhausted stop patterns.
- Do not expose an ETA from this result yet.

## Consequences

Clients can display structurally matched next stops while retaining the
evidence needed to distinguish exact from geometric fallback matches. ETA V0
can build on this projection, but must add timing evidence and confidence
limits before presenting arrival minutes.
