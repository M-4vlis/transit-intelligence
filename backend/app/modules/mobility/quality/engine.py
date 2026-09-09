from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.modules.mobility.models import QualityStatus, VehiclePosition


@dataclass(frozen=True, slots=True)
class QualityAssessment:
    status: QualityStatus
    score: float
    reasons: tuple[str, ...]


class VehicleQualityEngine:
    """Deterministic V0 quality assessment.

    V0 is intentionally simple and explainable. Statistical/route-aware signals are
    introduced only after we have stable ingestion and measured source behavior.
    """

    def __init__(
        self,
        *,
        stale_after: timedelta = timedelta(minutes=2),
        severely_stale_after: timedelta = timedelta(minutes=5),
        max_plausible_speed_mps: float = 45.0,  # 162 km/h: reject obvious GPS artifacts
        future_tolerance: timedelta = timedelta(seconds=30),
    ) -> None:
        self.stale_after = stale_after
        self.severely_stale_after = severely_stale_after
        self.max_plausible_speed_mps = max_plausible_speed_mps
        self.future_tolerance = future_tolerance

    def assess(
        self,
        position: VehiclePosition,
        *,
        now: datetime | None = None,
    ) -> QualityAssessment:
        now = now or datetime.now(timezone.utc)
        observed_at = position.observed_at
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=timezone.utc)

        reasons: list[str] = []
        score = 1.0
        invalid = False

        if observed_at > now + self.future_tolerance:
            invalid = True
            score -= 0.8
            reasons.append("timestamp_in_future")

        age = now - observed_at
        if age > self.severely_stale_after:
            score -= 0.75
            reasons.append("gps_severely_stale")
        elif age > self.stale_after:
            score -= 0.45
            reasons.append("gps_stale")

        if position.speed_mps is not None and position.speed_mps > self.max_plausible_speed_mps:
            score -= 0.5
            reasons.append("implausible_speed")

        score = max(0.0, min(1.0, score))

        if invalid or score < 0.25:
            status = QualityStatus.INVALID
        elif age > self.severely_stale_after:
            status = QualityStatus.STALE
        elif score < 0.8:
            status = QualityStatus.DEGRADED
        else:
            status = QualityStatus.GOOD

        return QualityAssessment(status=status, score=round(score, 4), reasons=tuple(reasons))

    def apply(
        self,
        position: VehiclePosition,
        *,
        now: datetime | None = None,
    ) -> VehiclePosition:
        assessment = self.assess(position, now=now)
        return position.model_copy(
            update={
                "quality_status": assessment.status,
                "quality_score": assessment.score,
            }
        )
