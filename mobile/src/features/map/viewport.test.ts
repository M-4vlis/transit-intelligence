import { describe, expect, it } from 'vitest';

import { centerAfterPan, clampZoom, projectToWorld } from './viewport';

describe('map viewport', () => {
  it('clamps zoom to the supported raster range', () => {
    expect(clampZoom(5)).toBe(12);
    expect(clampZoom(15.4)).toBe(15);
    expect(clampZoom(30)).toBe(17);
  });

  it('keeps the center unchanged when a pan has no displacement', () => {
    const center = { latitude: -22.904, longitude: -43.191 };
    const result = centerAfterPan(center, 0, 0, 14);
    expect(result.latitude).toBeCloseTo(center.latitude, 10);
    expect(result.longitude).toBeCloseTo(center.longitude, 10);
  });

  it('moves the geographic center west when the map is dragged east', () => {
    const center = { latitude: -22.904, longitude: -43.191 };
    expect(centerAfterPan(center, 100, 0, 14).longitude).toBeLessThan(center.longitude);
  });

  it('projects a larger world at higher zoom', () => {
    const point = { latitude: -22.904, longitude: -43.191 };
    expect(projectToWorld(point, 15).x).toBeCloseTo(projectToWorld(point, 14).x * 2);
  });
});
