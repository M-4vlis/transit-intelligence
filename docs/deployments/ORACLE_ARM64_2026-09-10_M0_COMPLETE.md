# Oracle ARM64 M0 completion — 2026-09-10

## Outcome

M0 Transit Core completed its production gate on the Oracle ARM64 host. The
system passed continuous realtime ingestion, durable archive, independent
restore, retention preflight, controlled retention and post-operation smoke.

## Soak evidence

- Window: `2026-09-09T17:23:55.635815Z` through
  `2026-09-10T17:23:57.740167Z`.
- Expected/minimum/observed cycles: 1,440 / 1,296 / 1,439.
- Successful/failed cycles: 1,439 / 0.
- Received/rejected records: 13,999,810 / 0.
- Persisted positions: 9,163,027.
- Cache updates: 12,400,381.
- Success ratio: 1.0.
- Rejection ratio: 0.0.
- Maximum gap: 82.088005 seconds.
- Contract fingerprint:
  `b8a3775b7ce4415241a1ba377303da6801f6c089d5c26dac8c370871465c1e33`.

## Archive and restore evidence

| UTC day | Rows | Bytes | SHA-256 |
|---|---:|---:|---|
| 2026-09-03 | 4,627,753 | 251,408,292 | `481ce5a44fc6d23e61d6bd9fb610c70afd3e7f30dac484d8b5bbb10feec93aa3` |
| 2026-09-04 | 9,265,866 | 500,997,317 | `decd3a71225216643fd211601a2e7eccaee59e8bc0a22ba82923acdb2b4aedc3` |
| 2026-09-05 | 6,634,310 | 356,255,348 | `93b2730b23482beff850ac36e4d7ff85abffc762666e9de060422b5826d07c44` |
| 2026-09-06 | 4,795,523 | 255,196,508 | `280e09e60fd1200e83e94b92982aee10962fcda5d5954a59fcf16f4becaedafe` |
| 2026-09-07 | 4,744,463 | 251,840,569 | `fef88aea02be21e0d44bd50dbcac358a46ce5dfa9e05ba6cd11bf1b554ef0eeb` |

Every restore matched its manifest row count, byte size and SHA-256. Temporary
restore files were removed. The private bucket contains 1.505 GB, below the
20 GB Always Free allowance.

## Retention evidence

- Cutoff: `2026-09-08` with `HOT_RETENTION_DAYS=2`.
- Dry-run candidates: 2026-09-03 through 2026-09-07.
- Dry-run protected days: none.
- Dry-run dropped days: none.
- Apply dropped exactly 2026-09-03 through 2026-09-07.
- Remaining hot partitions: 2026-09-08 through 2026-09-10.
- Root filesystem changed from 47% used to 30% used, with 68 GB available.
- `DESTRUCTIVE_RETENTION_ENABLED=false` was restored after the one-shot apply.

## Post-operation validation

- API readiness: database and cache true.
- Stack smoke: database, cache and recent position true.
- Latest checked ingestion cycle succeeded with live persistence, cache updates
  and the expected fingerprint.
- OCI budget actual/forecast alerts remain active at USD 0.01.
