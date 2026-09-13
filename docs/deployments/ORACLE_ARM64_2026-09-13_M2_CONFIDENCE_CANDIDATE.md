# Oracle ARM64 — M2 confidence candidate — 2026-09-13

## Outcome

The first M2 candidate is operational as a read-only replay diagnostic. It does
not change live ETA responses or the Android application. Seven production
cohorts produced 528 observed arrivals with representation in all three v2
candidate bands.

The aggregate direction is useful but not yet publishable:

| Candidate band | Outcomes | Weighted MAE |
| --- | ---: | ---: |
| high | 89 | 64.738 s |
| medium | 338 | 87.781 s |
| low | 101 | 241.511 s |

## Development and held-out split

Four development anchors were used to inspect the v1 score distribution and
choose more conservative v2 band boundaries: high at 90 or above, medium from
75 to 89 and low below 75. Three different anchors were then held out from that
choice.

The 254 held-out outcomes had weighted MAE of 70.407 seconds for high, 79.475
seconds for medium and 250.232 seconds for low. Low confidence is clearly
separated in this first sample, while the high/medium difference is small and
may be noise. Only four of seven individual cohorts were fully monotonic; one
held-out cohort had high MAE 91.529 seconds versus medium MAE 89.670 seconds.

Uncertainty interval coverage also remains insufficient and varied roughly
from 22% to 65% by cohort/band. No reliability claim is promoted.

## Diagnostic findings

- route/shape-pattern matching dominates exact-trip matching;
- speed dispersion is the most common candidate penalty;
- many anchors are excluded because the vehicle is more than 250 m from the
  matched shape;
- earlier-day rows were no longer in the hot database because proven retention
  had already archived them;
- archived history was not restored into production for this evaluation.

## Safety and verification

- candidate commits: `066f99e`, `d9257c6`, `30d68ef`;
- CI runs `34734902703`, `34735043884` and `34735249430` passed all jobs,
  including real PostgreSQL integration and ARM64 PostGIS build;
- only the isolated one-shot `eta-replay` image was rebuilt;
- API, PostgreSQL, Valkey, ingestion, edge and preview tunnel remained healthy
  with zero restarts;
- newest public position was approximately 42 seconds old after the runs;
- ETA profile refresh timer remained active;
- production environment checksum remained
  `800e640768673f08f3190719d868fbb8e5df3412508e91307776c4ddd384570a`;
- destructive retention settings were not changed;
- the separate APK distribution tunnel was stopped after successful physical
  device validation, while its artifact remains preserved.

## Decision

Keep `m2-candidate-v2` internal and uncalibrated. Accumulate independent-day
cohorts and either evaluate future hot windows or restore immutable Parquet into
a temporary isolated database. Do not expose confidence in the API or app until
high and medium separate reliably and uncertainty intervals are recalibrated.
