# Oracle ARM64 production hotfix - 2026-09-09

## Outcome

- Permanent SSH access was restored on TCP 443 using an Ed25519 key and a host
  firewall rule restricted to the operator workstation IP.
- The host was confirmed as Ubuntu 24.04.4 LTS on `aarch64` with 12 GB RAM.
- PostgreSQL/PostGIS, Valkey, API and Rio ingestion are healthy.
- API readiness confirms both database and cache connectivity.
- The boot volume was expanded online from 47 GB to 100 GB. Combined tenancy
  boot volume use is 147 GB and OCI marks the Transit volume as free-tier retained.
- Root filesystem capacity is 96 GB with 58 GB available after expansion.

## Realtime evidence

- The official Rio endpoint returned HTTP 200 with the required UTC
  `dataInicial` and `dataFinal` query parameters.
- A two-minute live request returned valid JSON with 15,158 records.
- Recent production cycles persist approximately 7,000-7,500 new positions and
  refresh approximately 10,000 cache entries per minute.
- Contract fingerprint remained stable at prefix `b8a3775b7ce44152`.
- Valkey returned PONG and contained real `mobility:v1:vehicle:*` keys.

## Durable archive and restore evidence

- OCI S3-compatible smoke upload/download/hash verification passed.
- UTC day `2026-09-03` was archived without deleting hot data.
- Remote object row count: 4,627,753.
- Remote object bytes: 251,408,292.
- SHA-256: `481ce5a44fc6d23e61d6bd9fb610c70afd3e7f30dac484d8b5bbb10feec93aa3`.
- Full restore matched row count, byte size and SHA-256, then removed its local
  temporary copy.

## Soak

- The invalidated prior run was preserved under
  `ops/soak-invalidated-20260909T172307Z`.
- A fresh persistent watcher started from the first qualifying production cycle
  at `2026-09-09T17:23:55.635815Z`.
- Expected evaluation time is approximately `2026-09-10T17:23:55Z`.

## Safety state

- `DESTRUCTIVE_RETENTION_ENABLED=false`.
- No historical partition was dropped.
- Recovery PARs, temporary Object Storage objects/bucket, ephemeral private keys
  and the active serial console connection were removed after permanent SSH was
  verified.
