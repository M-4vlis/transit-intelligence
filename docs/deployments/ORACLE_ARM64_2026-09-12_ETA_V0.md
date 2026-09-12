# Oracle ARM64 — experimental ETA V0 — 2026-09-12

## Outcome

The public upcoming-stop endpoint now includes bounded experimental ETA,
speed evidence, observation age, an uncertainty interval and explicit
unavailability reasons. The Android package has not been changed yet.

## Verification

- implementation commits: `dedfe10`, `cae3164`;
- final CI run: `34703288294` (`success`), including real PostGIS and
  PostgreSQL speed-evidence tests;
- local suite: 119 passed, 6 integration tests deselected;
- only the API image and container were replaced;
- live vehicle `A72050`, route `O0422AAA0A`, shape `n6im`;
- match method: `route_shape_pattern`, projection gap: approximately 0.8 m;
- evidence: 12 samples from the same vehicle over five minutes;
- first future stop: `Ancine`, approximately 320.8 m ahead;
- point ETA: 6 seconds; experimental interval: 0–34 seconds;
- a live vehicle without a shape returned `missing_shape_id`, no ETA evidence
  and no fabricated stop prediction;
- API health: healthy, zero restarts;
- final stack smoke passed database, cache and recent-position checks;
- all six long-running services active;
- production environment SHA-256 unchanged;
- destructive retention remained disabled.

The first CI attempt correctly rejected an ambiguous temporal parameter type
in PostgreSQL. Explicit timestamp and interval casts were added before any
production deployment.
