# Oracle ARM64 — acknowledged realtime windows — 2026-09-12

## Outcome

Realtime ingestion now advances its source window only after quarantine,
PostgreSQL and Valkey writes have all completed. A failed cycle retains the
exact pending window for a safe retry; existing database deduplication and
Latest Position Wins cache semantics make that replay idempotent.

## Verification

- commit: `a1ed2dc`;
- CI run: `34699241864` (`success`);
- local unit suite: 112 passed, 4 integration tests deselected;
- only the `rio-ingestion` image and service were rebuilt/restarted;
- the existing worker lease was allowed to expire naturally;
- first live cycle: 10,836 received, 190 deduplicated, 10,646 persisted,
  10,241 cache updates and zero rejected;
- second live cycle: 7,950 received, 158 deduplicated, 5,326 persisted,
  7,238 cache updates and zero rejected;
- the second request began with the configured 30-second overlap, proving that
  a successful acknowledgement advanced the cursor;
- stack smoke passed database, cache and recent-position checks, with a latest
  observation age of approximately 10 seconds;
- the production environment file hash was unchanged.

Failure/replay behavior is covered by deterministic repository, cache and
quarantine failure tests. No production fault was deliberately induced.
Destructive retention remains disabled.
