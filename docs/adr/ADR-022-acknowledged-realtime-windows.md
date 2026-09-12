# ADR-022 — Acknowledged realtime source windows

## Status

Accepted on 2026-09-12.

## Context

The Rio adapter previously advanced its in-memory source cursor immediately
after a valid HTTP response. A later PostgreSQL or Valkey failure therefore
made the next cycle move forward even though the fetched window had not fully
reached durable and live storage. The overlap reduced, but did not eliminate,
the possible gap.

## Decision

Use at-least-once source-window delivery inside each worker process.

- a successful fetch creates a pending exact window;
- the ingestion service acknowledges it only after quarantine, position
  persistence and live-cache writes complete;
- any downstream exception leaves the window pending;
- the next cycle fetches the exact same start and end timestamps;
- an acknowledgement must match the pending batch timestamp;
- the position repository deduplication key and Latest Position Wins cache make
  replay safe.

HTTP/schema failures before a batch exists continue to leave the cursor at its
last acknowledged point. Worker restart still begins with the configured
bounded recovery window; durable cursor storage is not required for ETA V0.

## Consequences

Transient database and cache failures no longer silently skip a fetched source
window. A failed window may cause one extra request and repeated quarantine
upserts, which is preferable to a gap in the operational history. Persistent
failures deliberately keep retrying the unacknowledged window and remain
visible through ingestion failure metrics and logs.
