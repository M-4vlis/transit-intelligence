import { useCallback, useEffect, useState } from 'react';

import { transitApi } from '@/api/client';
import type { NearbyStop, VehiclePosition } from '@/api/types';

import type { MapCenter } from './types';

export function useNearbyTransit(center: MapCenter) {
  const [stops, setStops] = useState<NearbyStop[]>([]);
  const [vehicles, setVehicles] = useState<VehiclePosition[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [stopPage, nearbyVehicles] = await Promise.all([
        transitApi.nearbyStops(center.latitude, center.longitude),
        transitApi.nearbyVehicles(center.latitude, center.longitude),
      ]);
      setStops(stopPage.items);
      setVehicles(nearbyVehicles);
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Não foi possível atualizar o mapa.');
    } finally {
      setLoading(false);
    }
  }, [center.latitude, center.longitude]);

  useEffect(() => {
    const initialRefresh = setTimeout(() => void refresh(), 0);
    const interval = setInterval(() => void refresh(), 30_000);
    return () => {
      clearTimeout(initialRefresh);
      clearInterval(interval);
    };
  }, [refresh]);

  return { stops, vehicles, loading, error, refresh };
}
