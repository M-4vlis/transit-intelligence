import { useCallback, useRef, useState } from 'react';

import { transitApi } from '@/api/client';
import type { VehicleJourneyMatch, VehiclePosition } from '@/api/types';

export function useVehicleEta() {
  const requestSequence = useRef(0);
  const [vehicle, setVehicle] = useState<VehiclePosition | null>(null);
  const [journey, setJourney] = useState<VehicleJourneyMatch | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (nextVehicle: VehiclePosition) => {
    const requestId = ++requestSequence.current;
    setVehicle(nextVehicle);
    setJourney(null);
    setError(null);
    setLoading(true);
    try {
      const result = await transitApi.upcomingStops(
        nextVehicle.route_id,
        nextVehicle.vehicle_id,
      );
      if (requestSequence.current === requestId) {
        setJourney(result);
      }
    } catch (caught) {
      if (requestSequence.current === requestId) {
        setError(caught instanceof Error ? caught.message : 'Não foi possível consultar o ETA.');
      }
    } finally {
      if (requestSequence.current === requestId) {
        setLoading(false);
      }
    }
  }, []);

  const clear = useCallback(() => {
    requestSequence.current += 1;
    setVehicle(null);
    setJourney(null);
    setError(null);
    setLoading(false);
  }, []);

  return { vehicle, journey, loading, error, load, clear };
}
