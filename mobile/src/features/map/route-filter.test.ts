import { describe, expect, it } from 'vitest';

import { presentRouteLabel, uniqueRouteIds } from './route-filter';

describe('map route filter', () => {
  it('presents Rio route identifiers as passenger-facing numbers', () => {
    expect(presentRouteLabel('O0870AAA0A')).toBe('870');
    expect(presentRouteLabel('O0388AAA0A')).toBe('388');
    expect(presentRouteLabel('457')).toBe('457');
  });

  it('deduplicates and naturally sorts route identifiers', () => {
    expect(uniqueRouteIds(['O0870AAA0A', 'O0388AAA0A', 'O0870AAA0A'])).toEqual([
      'O0388AAA0A',
      'O0870AAA0A',
    ]);
  });
});
