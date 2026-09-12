import type { MapCenter } from './types';

export const TILE_SIZE = 256;
export const DEFAULT_ZOOM = 14;
export const MIN_ZOOM = 12;
export const MAX_ZOOM = 17;

const MAX_LATITUDE = 85.05112878;

interface PixelPoint {
  x: number;
  y: number;
}

export function clampZoom(zoom: number) {
  return Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, Math.round(zoom)));
}

export function projectToWorld(
  { latitude, longitude }: MapCenter,
  zoom: number,
): PixelPoint {
  const scale = TILE_SIZE * 2 ** clampZoom(zoom);
  const boundedLatitude = Math.max(-MAX_LATITUDE, Math.min(MAX_LATITUDE, latitude));
  const latitudeRadians = (boundedLatitude * Math.PI) / 180;

  return {
    x: ((longitude + 180) / 360) * scale,
    y:
      ((1 -
        Math.log(Math.tan(latitudeRadians) + 1 / Math.cos(latitudeRadians)) / Math.PI) /
        2) *
      scale,
  };
}

function unprojectFromWorld({ x, y }: PixelPoint, zoom: number): MapCenter {
  const scale = TILE_SIZE * 2 ** clampZoom(zoom);
  const longitude = (x / scale) * 360 - 180;
  const mercator = Math.PI * (1 - (2 * y) / scale);
  const latitude = (Math.atan(Math.sinh(mercator)) * 180) / Math.PI;
  return { latitude, longitude };
}

export function centerAfterPan(
  center: MapCenter,
  deltaX: number,
  deltaY: number,
  zoom: number,
): MapCenter {
  const centerPixel = projectToWorld(center, zoom);
  return unprojectFromWorld(
    { x: centerPixel.x - deltaX, y: centerPixel.y - deltaY },
    zoom,
  );
}
