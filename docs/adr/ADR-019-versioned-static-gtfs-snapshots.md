# ADR-019 — Versioned static GTFS snapshots

## Status

Accepted on 2026-09-03.

## Context

The product must combine scheduled network structure with realtime positions to
estimate arrival and communicate confidence. The official static GTFS was
originally published as a public ArcGIS item.

On 2026-09-11 that item returned HTTP 403 because it had become private. The
municipality's replacement public ArcGIS metadata item points to the canonical
download endpoint `https://dados.mobilidade.rio/gtfs/schedule`. The dedicated
allowlist follows that canonical hostname rather than retaining the private item.

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
content is idempotent. All versioned rows are imported in one database
transaction; only a fully imported snapshot can become active. Activation and
rollback change a single catalog pointer transactionally, so API reads never mix
two schedule versions.

## Consequences

We can prepare routes, stops, trips and schedules without weakening the live
data gate. A malformed or unexpectedly large upstream artifact fails closed.
No destructive retention setting changes as a consequence of this decision.
