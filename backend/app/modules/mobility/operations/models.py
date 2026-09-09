from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class IngestionRunSample:
    status: str
    started_at: datetime
    finished_at: datetime
    received_records: int
    rejected_records: int
    persisted_records: int
    cached_records: int
    contract_fingerprint: str | None


@dataclass(frozen=True, slots=True)
class SoakThresholds:
    min_cycle_coverage: float = 0.90
    min_success_ratio: float = 0.98
    max_rejection_ratio: float = 0.02
    max_gap_seconds: float = 180.0
    max_latest_age_seconds: float = 120.0
    max_contract_fingerprints: int = 1

    def validate(self) -> None:
        for name in ("min_cycle_coverage", "min_success_ratio", "max_rejection_ratio"):
            value = getattr(self, name)
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.max_gap_seconds <= 0 or self.max_latest_age_seconds <= 0:
            raise ValueError("soak timing thresholds must be positive")
        if self.max_contract_fingerprints < 1:
            raise ValueError("max_contract_fingerprints must be at least 1")


@dataclass(frozen=True, slots=True)
class SoakAssessment:
    passed: bool
    reasons: tuple[str, ...]
    observed_hours: float
    expected_runs: int
    minimum_runs: int
    total_runs: int
    successful_runs: int
    failed_runs: int
    success_ratio: float
    total_received_records: int
    total_rejected_records: int
    rejection_ratio: float
    total_persisted_records: int
    total_cached_records: int
    unique_contract_fingerprints: tuple[str, ...]
    max_gap_seconds: float | None
    latest_run_age_seconds: float | None
