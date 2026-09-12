import { describe, expect, it } from 'vitest';

import { selectDecluttered } from './declutter';

describe('map marker decluttering', () => {
  it('keeps one marker per screen cell and ignores off-screen items', () => {
    const items = [
      { id: 'first', left: 10, top: 10 },
      { id: 'overlap', left: 18, top: 18 },
      { id: 'second', left: 50, top: 10 },
      { id: 'outside', left: 150, top: 10 },
    ];

    const selected = selectDecluttered(
      items,
      (item) => ({ left: item.left, top: item.top }),
      { width: 100, height: 100 },
      32,
      10,
    );

    expect(selected.map(({ item }) => item.id)).toEqual(['first', 'second']);
  });

  it('respects the maximum marker count', () => {
    const items = Array.from({ length: 10 }, (_, index) => ({ index }));
    expect(
      selectDecluttered(
        items,
        ({ index }) => ({ left: index * 20, top: 1 }),
        { width: 500, height: 100 },
        10,
        3,
      ),
    ).toHaveLength(3);
  });
});
