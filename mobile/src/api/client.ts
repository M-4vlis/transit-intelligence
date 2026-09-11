import { getApiBaseUrl } from '@/config/runtime';

import type { GtfsRoute, NearbyStop, Page, VehiclePosition } from './types';

const REQUEST_TIMEOUT_MS = 10_000;

async function getJson<T>(path: string, params: Record<string, string | number>): Promise<T> {
  const query = new URLSearchParams(
    Object.entries(params).map(([key, value]) => [key, String(value)]),
  );
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(`${getApiBaseUrl()}${path}?${query}`, {
      headers: { Accept: 'application/json' },
      signal: controller.signal,
    });
    if (!response.ok) {
      throw new Error(`A API respondeu com HTTP ${response.status}.`);
    }
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      throw new Error('A API demorou demais para responder.');
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

export const transitApi = {
  nearbyStops(latitude: number, longitude: number, radiusM = 1200) {
    return getJson<Page<NearbyStop>>('/v1/stops/nearby', {
      latitude,
      longitude,
      radius_m: radiusM,
      limit: 100,
    });
  },

  nearbyVehicles(latitude: number, longitude: number, radiusM = 3000) {
    return getJson<VehiclePosition[]>('/v1/vehicles/nearby', {
      latitude,
      longitude,
      radius_m: radiusM,
      max_age_seconds: 180,
      limit: 200,
    });
  },

  searchRoutes(query: string) {
    return getJson<Page<GtfsRoute>>('/v1/routes', {
      query,
      limit: 50,
      offset: 0,
    });
  },

  vehiclesByRoute(routeId: string) {
    return getJson<VehiclePosition[]>(`/v1/routes/${encodeURIComponent(routeId)}/vehicles`, {});
  },
};
