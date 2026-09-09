# ADR-019 — Versioned static GTFS snapshots

## Status

Accepted on 2026-09-03.

## Context

The product must eventually combine scheduled network structure with realtime
positions to estimate arrival and communicate confidence. The Rio realtime
endpoint is currently returning HTTP 500, but the official static GTFS remains
available through the municipality's public ArcGIS item.

Static data is useful parallel progress, but it cannot be used as evidence that
the realtime ingestion gate or its 24-hour soak has passed.

## Decision

Acquire the Rio GTFS through a separate adapter boundary with:

- HTTPS and a dedicated hostname allowlist;
- bounded streaming download with no automatic redirects;
- SHA-256 content identity and a versioned provenance manifest;
- CC BY 4.0 license and SMTR attribution recorded in the manifest;
- strict ZIP, member, size and required-schema validation;
- a production maintenance canary isolated from database and cache networks.

The SHA-256 digest is the snapshot identifier. Repeated acquisition of identical
content is idempotent. Import into PostGIS and use by ETA models are separate
milestones and require their own migrations and validation.

## Consequences

We can prepare routes, stops, trips and schedules without weakening the live
data gate. A malformed or unexpectedly large upstream artifact fails closed.
No destructive retention setting changes as a consequence of this decision.
