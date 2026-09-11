import { describe, expect, it } from 'vitest';

import { formatAge, positionAgeSeconds, presentGpsQuality } from './gps-quality';

const NOW = Date.parse('2026-09-11T15:00:00Z');

describe('GPS quality presentation', () => {
  it('keeps a recent good position trustworthy', () => {
    const result = presentGpsQuality(
      { observed_at: '2026-09-11T14:59:40Z', quality_status: 'good' },
      NOW,
    );
    expect(result).toMatchObject({ status: 'good', ageSeconds: 20, label: 'GPS atual' });
  });

  it('degrades an otherwise good position when its age grows', () => {
    const result = presentGpsQuality(
      { observed_at: '2026-09-11T14:58:00Z', quality_status: 'good' },
      NOW,
    );
    expect(result.status).toBe('degraded');
  });

  it('marks positions older than five minutes as stale', () => {
    const result = presentGpsQuality(
      { observed_at: '2026-09-11T14:54:00Z', quality_status: 'degraded' },
      NOW,
    );
    expect(result.status).toBe('stale');
  });

  it('handles malformed and future timestamps safely', () => {
    expect(positionAgeSeconds('not-a-date', NOW)).toBeNull();
    expect(positionAgeSeconds('2026-09-11T15:01:00Z', NOW)).toBe(0);
    expect(formatAge(125)).toBe('há 2 min');
  });
});
