# Oracle ARM64 — GTFS stop distances — 2026-09-12

## Outcome

The active GTFS snapshot now has complete stop distance evidence for ETA V0.
The maintenance operation downloads and validates the official archive, then
requires its SHA-256 and every stop-time key to match the active database
snapshot before making any change in one transaction.

## Verification

- active and official snapshot:
  `a99f925460e7628b6eeecb9952430542c06b3e2800afa8ba7f9765fd2e6f26f1`;
- deployment commit: `417db7c`;
- CI run: `34700130989` (`success`);
- staged rows: 1,031,419;
- source rows with distance: 1,031,419 (100%);
- target rows with distance after commit: 1,031,419 (100%);
- source null distances: zero;
- distance range: 0 to 80,253.18;
- negative or decreasing distances per trip: rejected transactionally;
- source/database key mismatch: rejected transactionally;
- production environment SHA-256 unchanged;
- destructive retention remained disabled.

Two pre-commit attempts exposed a temporary-schema qualification issue and an
ambiguous SQL column. Both transactions rolled back before changing permanent
data; each correction passed the full CI before retrying.

The final million-row update temporarily saturated database I/O, causing the
realtime writer to time out. The acknowledged-window mechanism replayed the
same source window until persistence succeeded, then caught up without data
loss. Final stack smoke passed database, cache and recent-position checks with
a latest-position age of approximately 42 seconds. All six long-running
services remained active.
