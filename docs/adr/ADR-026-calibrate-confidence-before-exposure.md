# ADR-026 — Calibrate confidence before public exposure

## Context

ETA V0 exposes point and percentile-based interval estimates, but the first
production replay showed material error and low interval coverage. A score made
only from plausible engineering weights could look authoritative without being
predictive.

## Decision

Introduce the first confidence formula as an internal candidate only. It scores
six observable factors: position recency, shape projection distance, evidence
method, sample support, speed dispersion and journey-match method.

The read-only replay groups future arrival errors by candidate band and reports
MAE, P90 and interval coverage. The candidate remains explicitly
`uncalibrated`; it is not added to the public API or mobile UI until held-out
cohorts demonstrate useful error separation and adequate representation.

Weights, thresholds and diagnostic reason codes live in a pure domain function
with deterministic tests. Calibration may replace the formula without changing
the existing ETA calculation or persistence.

## Consequences

- M2 can be evaluated against real outcomes before making a user-facing claim.
- Replays remain read-only and do not alter live ETA or collection.
- A high raw score is not yet a confidence guarantee.
- Interval calibration and bias correction remain separate required work.
