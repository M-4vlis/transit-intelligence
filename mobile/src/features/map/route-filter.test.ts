import { describe, expect, it } from 'vitest';

import { presentRouteLabel, uniqueRouteLabels } from './route-filter';

describe('map route filter', () => {
  it('presents Rio route identifiers as passenger-facing numbers', () => {
    expect(presentRouteLabel('O0870AAA0A')).toBe('870');
    expect(presentRouteLabel('O0388AAA0A')).toBe('388');
    expect(presentRouteLabel('457')).toBe('457');
  });

  it('groups direction variants under one passenger-facing label', () => {
    expect(
      uniqueRouteLabels(['O0884AAA0A', 'O0388AAA0A', 'O0884BAA0A', 'O0870AAA0A']),
    ).toEqual(['388', '870', '884']);
  });
});
