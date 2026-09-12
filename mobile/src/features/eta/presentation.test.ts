import { describe, expect, it } from 'vitest';

import type { UpcomingStop } from '@/api/types';

import { presentEta, presentJourneyUnavailable } from './presentation';

function stop(overrides: Partial<UpcomingStop> = {}): UpcomingStop {
  return {
    stop_id: 'S1',
    stop_name: 'Central',
    latitude: -22.9,
    longitude: -43.2,
    stop_sequence: 1,
    shape_dist_traveled: 100,
    shape_distance_ahead: 50,
    estimated_arrival_at: null,
    eta_seconds: 70,
    eta_lower_seconds: 40,
    eta_upper_seconds: 110,
    eta_unavailable_reason: null,
    ...overrides,
  };
}

describe('ETA presentation', () => {
  it('labels the point estimate and interval as experimental', () => {
    expect(presentEta(stop())).toEqual({ eta: '2 min', detail: 'faixa experimental 0–2 min' });
  });

  it('uses an honest unavailable reason instead of inventing an ETA', () => {
    expect(
      presentEta(
        stop({
          eta_seconds: null,
          eta_lower_seconds: null,
          eta_upper_seconds: null,
          eta_unavailable_reason: 'stale_position',
        }),
      ),
    ).toEqual({ eta: 'Sem ETA', detail: 'GPS antigo' });
    expect(presentJourneyUnavailable('vehicle_off_shape')).toContain('distante');
  });
});
