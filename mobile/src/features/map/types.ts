import type { NearbyStop, VehiclePosition } from '@/api/types';

export interface MapCenter {
  latitude: number;
  longitude: number;
}

export interface TransitMapProps {
  center: MapCenter;
  stops: NearbyStop[];
  vehicles: VehiclePosition[];
  userLocation?: MapCenter | null;
  onCenterChange?: (center: MapCenter) => void;
  onVehiclePress?: (vehicle: VehiclePosition) => void;
}

export interface MapProviderAdapter {
  Surface: React.ComponentType<TransitMapProps>;
  providerName: string;
}
