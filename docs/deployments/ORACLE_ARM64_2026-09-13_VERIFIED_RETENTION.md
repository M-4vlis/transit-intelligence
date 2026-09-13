# Oracle ARM64 verified retention — 2026-09-13

## Outcome

The explicitly authorized production policy is active with
`HOT_RETENTION_DAYS=7` and `DESTRUCTIVE_RETENTION_ENABLED=true`. No partition
was eligible or removed during activation. Cold objects are never deleted by
this workflow.

The production environment file remains mode `0600`; its post-change SHA-256
is `4135a4a891ea12af518ffdbe46a609010b5f0bedda4ff8650808b5275f981e30`.

## Fail-closed sequence

The daily systemd job performs:

1. idempotent archive review of the previous eight UTC days;
2. full independent restore of yesterday's Parquet;
3. read-only retention preflight;
4. abort if any candidate is protected;
5. retention apply with a second live remote verification and locked row-count
   comparison.

The job is serialized with `flock`, runs at low host priority, and its Compose
workers have CPU and memory limits. The timer is enabled, active and scheduled
for `03:10 UTC` with a bounded randomized delay.

## Activation evidence

- Seven-day preflight cutoff: `2026-09-06`.
- Candidate, protected and would-drop days: none.
- Controlled apply dropped days: none.
- Remaining hot partitions: `2026-09-08` through `2026-09-13`.
- First current partition that can become eligible: `2026-09-08`, no earlier
  than the `2026-09-16` UTC cycle.

The real systemd service then completed the full sequence successfully. It
found the eight reviewed days idempotently verified, restored `2026-09-12`,
passed preflight and again applied zero deletions.

## New archive and restore evidence

| UTC day | Rows | Bytes | SHA-256 |
|---|---:|---:|---|
| 2026-09-08 | 7,126,264 | 383,050,051 | `836ccebb26574969f7a2eba5c9e037a452a8fb91ed46fd53df50cc90df3550d4` |
| 2026-09-09 | 8,966,997 | 493,602,754 | `2b91cc9099ed4f09e47c7f1227a6acef5e41d102562689abe7ba85d10fdaef5d` |
| 2026-09-10 | 8,984,235 | 494,679,848 | `24c93bc112411d559886a276fff468d28e311254919deff6dd44fe2d7464c560` |
| 2026-09-11 | 9,012,516 | 496,444,665 | `fe9ca1f65da08d87381a0fd95bbe9368dd9ac2f88b370c585d2fe379e02e3c63` |
| 2026-09-12 | 6,678,247 | 368,501,497 | `a410fa1f2993e62d03db5ed8bf8b43024fc5e725673f812a8f83bdeb30c106ef` |

Every object passed full download, Parquet row count, byte size and SHA-256.
Together with the earlier evidence, the manifest has 11 verified entries,
70,836,174 rows and 3,851,978,368 bytes; one entry is the valid empty
pre-ingestion day.

## Load finding and correction

The first catch-up attempt exposed database write timeouts while the archive
query forced a sort of millions of historical rows. The attempt was stopped;
no hot partition was deleted. The historical export was changed to stream the
already bounded UTC partition without an unnecessary order, and the archive
container was limited to 0.5 CPU and 2 GiB.

After that correction, the complete `2026-09-09` through `2026-09-12` archive
and restore workload overlapped 45 observed ingestion cycles: 45 succeeded,
zero failed and zero records were rejected. The contract fingerprint remained
`b8a3775b7ce4415241a1ba377303da6801f6c089d5c26dac8c370871465c1e33`.

## Final health and budget

- API readiness: database and cache true.
- PostgreSQL, Valkey, API, ingestion and edge proxy healthy; quick tunnel
  running.
- Official Rio check: 7,864 received/valid, zero rejected, expected fields and
  stable fingerprint.
- Operations report: `passed`, no failures or warnings; verified-retention
  service healthy.
- Root filesystem: 46% used, 53 GiB available.
- Host memory: approximately 10 GiB available after maintenance.
- Object Storage: 3,852,700,322 bytes across 75 objects; 10 complete Parquet
  objects use 3,851,976,849 bytes.
- Thirty-day projection: 15,735,656,762 bytes, below the documented 20 GB
  Always Free ceiling but above the project's conservative 10 GB warning.
- Projected M2 requests: 21,480/month, below both the 30,000 operational budget
  and 50,000 free-tier limit.

## Verification

- Local suite: 160 passed, 9 external-integration tests skipped.
- Ruff: passed.
- Production Compose configuration: valid.
- Bash and systemd unit verification: passed; unrelated executable-bit warnings
  came only from Oracle's preinstalled monitoring agent units.
- GitHub CI passed the retention automation and self-healing archive changes:
  <https://github.com/M-4vlis/transit-intelligence/actions/runs/34776310572>.
