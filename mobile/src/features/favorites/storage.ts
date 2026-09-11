import AsyncStorage from '@react-native-async-storage/async-storage';

import type { GtfsRoute } from '@/api/types';

const STORAGE_KEY = 'transit-intelligence/favorite-routes/v1';

export interface FavoriteRoute {
  routeId: string;
  shortName: string;
  longName: string;
}

export function routeToFavorite(route: GtfsRoute): FavoriteRoute {
  return {
    routeId: route.route_id,
    shortName: route.route_short_name || route.route_id,
    longName: route.route_long_name || 'Itinerário sem nome',
  };
}

function isFavoriteRoute(value: unknown): value is FavoriteRoute {
  if (!value || typeof value !== 'object') return false;
  const item = value as Record<string, unknown>;
  return ['routeId', 'shortName', 'longName'].every((key) => typeof item[key] === 'string');
}

export async function loadFavoriteRoutes(): Promise<FavoriteRoute[]> {
  const raw = await AsyncStorage.getItem(STORAGE_KEY);
  if (!raw) return [];
  try {
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter(isFavoriteRoute) : [];
  } catch {
    return [];
  }
}

export async function toggleFavoriteRoute(route: FavoriteRoute): Promise<FavoriteRoute[]> {
  const current = await loadFavoriteRoutes();
  const exists = current.some((item) => item.routeId === route.routeId);
  const next = exists
    ? current.filter((item) => item.routeId !== route.routeId)
    : [...current, route].sort((a, b) => a.shortName.localeCompare(b.shortName));
  await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  return next;
}
