import type { QualityStatus, VehiclePosition } from '@/api/types';

export interface GpsQualityPresentation {
  ageSeconds: number | null;
  status: QualityStatus;
  label: string;
  detail: string;
}

export function positionAgeSeconds(observedAt: string, nowMs = Date.now()): number | null {
  const observedMs = Date.parse(observedAt);
  if (!Number.isFinite(observedMs)) return null;
  return Math.max(0, Math.floor((nowMs - observedMs) / 1000));
}

export function presentGpsQuality(
  position: Pick<VehiclePosition, 'observed_at' | 'quality_status'>,
  nowMs = Date.now(),
): GpsQualityPresentation {
  const ageSeconds = positionAgeSeconds(position.observed_at, nowMs);
  if (ageSeconds === null || position.quality_status === 'invalid') {
    return { ageSeconds, status: 'invalid', label: 'GPS inválido', detail: 'Não usar esta posição.' };
  }

  const status: QualityStatus =
    ageSeconds > 300
      ? 'stale'
      : ageSeconds > 90 && position.quality_status === 'good'
        ? 'degraded'
        : position.quality_status;

  if (status === 'good') {
    return { ageSeconds, status, label: 'GPS atual', detail: formatAge(ageSeconds) };
  }
  if (status === 'degraded') {
    return { ageSeconds, status, label: 'GPS com atraso', detail: formatAge(ageSeconds) };
  }
  return { ageSeconds, status: 'stale', label: 'GPS antigo', detail: formatAge(ageSeconds) };
}

export function formatAge(ageSeconds: number): string {
  if (ageSeconds < 60) return `há ${ageSeconds} s`;
  const minutes = Math.floor(ageSeconds / 60);
  return `há ${minutes} min`;
}
