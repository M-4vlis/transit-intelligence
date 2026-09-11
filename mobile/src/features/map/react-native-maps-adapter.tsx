import MapView, { Marker, type Region } from 'react-native-maps';
import { StyleSheet, View } from 'react-native';

import { colors } from '@/constants/theme';
import { presentGpsQuality } from '@/features/quality/gps-quality';

import type { MapProviderAdapter, TransitMapProps } from './types';

function ReactNativeMapsSurface({ center, stops, vehicles, onCenterChange }: TransitMapProps) {
  const initialRegion: Region = {
    ...center,
    latitudeDelta: 0.045,
    longitudeDelta: 0.045,
  };

  return (
    <MapView
      accessibilityLabel="Mapa com ônibus e pontos próximos"
      initialRegion={initialRegion}
      onRegionChangeComplete={({ latitude, longitude }) =>
        onCenterChange?.({ latitude, longitude })
      }
      style={StyleSheet.absoluteFill}>
      {stops.map((stop) => (
        <Marker
          key={`stop-${stop.stop_id}`}
          coordinate={{ latitude: stop.latitude, longitude: stop.longitude }}
          title={stop.stop_name}
          description={`${Math.round(stop.distance_m)} m do centro do mapa`}>
          <View style={styles.stopMarker} />
        </Marker>
      ))}
      {vehicles.map((vehicle) => {
        const quality = presentGpsQuality(vehicle);
        const markerColor =
          quality.status === 'good'
            ? colors.good
            : quality.status === 'degraded'
              ? colors.degraded
              : colors.stale;
        return (
          <Marker
            key={`vehicle-${vehicle.agency_id}-${vehicle.vehicle_id}`}
            coordinate={{ latitude: vehicle.latitude, longitude: vehicle.longitude }}
            title={`Linha ${vehicle.route_id}`}
            description={`${vehicle.vehicle_id} · ${quality.label} ${quality.detail}`}>
            <View style={[styles.vehicleMarker, { backgroundColor: markerColor }]} />
          </Marker>
        );
      })}
    </MapView>
  );
}

const styles = StyleSheet.create({
  stopMarker: {
    width: 12,
    height: 12,
    borderRadius: 6,
    backgroundColor: colors.stop,
    borderWidth: 2,
    borderColor: colors.surface,
  },
  vehicleMarker: {
    width: 18,
    height: 18,
    borderRadius: 5,
    borderWidth: 2,
    borderColor: colors.surface,
    transform: [{ rotate: '45deg' }],
  },
});

export const reactNativeMapsAdapter: MapProviderAdapter = {
  Surface: ReactNativeMapsSurface,
  providerName: 'react-native-maps',
};
