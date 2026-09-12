import { useMemo, useState } from 'react';
import { Image, StyleSheet, Text, View, type LayoutChangeEvent } from 'react-native';

import { colors } from '@/constants/theme';
import { getApiBaseUrl } from '@/config/runtime';
import { presentGpsQuality } from '@/features/quality/gps-quality';

import type { MapCenter, MapProviderAdapter, TransitMapProps } from './types';

const TILE_SIZE = 256;
const ZOOM = 14;
const MAX_LATITUDE = 85.05112878;

interface PixelPoint {
  x: number;
  y: number;
}

interface ViewportSize {
  width: number;
  height: number;
}

interface RasterTile {
  key: string;
  left: number;
  top: number;
  uri: string;
}

function projectToWorld({ latitude, longitude }: MapCenter): PixelPoint {
  const scale = TILE_SIZE * 2 ** ZOOM;
  const boundedLatitude = Math.max(-MAX_LATITUDE, Math.min(MAX_LATITUDE, latitude));
  const latitudeRadians = (boundedLatitude * Math.PI) / 180;

  return {
    x: ((longitude + 180) / 360) * scale,
    y:
      (1 - Math.log(Math.tan(latitudeRadians) + 1 / Math.cos(latitudeRadians)) / Math.PI) /
      2 *
      scale,
  };
}

function OsmRasterMapSurface({ center, stops, vehicles }: TransitMapProps) {
  const [viewport, setViewport] = useState<ViewportSize>({ width: 0, height: 0 });
  const [tileErrors, setTileErrors] = useState(0);
  const tileBaseUrl = getApiBaseUrl();

  const scene = useMemo(() => {
    if (viewport.width === 0 || viewport.height === 0) {
      return null;
    }

    const centerPixel = projectToWorld(center);
    const left = centerPixel.x - viewport.width / 2;
    const top = centerPixel.y - viewport.height / 2;
    const minimumTileX = Math.floor(left / TILE_SIZE);
    const maximumTileX = Math.floor((left + viewport.width) / TILE_SIZE);
    const minimumTileY = Math.floor(top / TILE_SIZE);
    const maximumTileY = Math.floor((top + viewport.height) / TILE_SIZE);
    const tileCount = 2 ** ZOOM;
    const tiles: RasterTile[] = [];

    for (let tileY = minimumTileY; tileY <= maximumTileY; tileY += 1) {
      if (tileY < 0 || tileY >= tileCount) {
        continue;
      }
      for (let tileX = minimumTileX; tileX <= maximumTileX; tileX += 1) {
        const wrappedTileX = ((tileX % tileCount) + tileCount) % tileCount;
        tiles.push({
          key: `${ZOOM}-${tileX}-${tileY}`,
          left: tileX * TILE_SIZE - left,
          top: tileY * TILE_SIZE - top,
          uri: `${tileBaseUrl}/v1/map/tiles/${ZOOM}/${wrappedTileX}/${tileY}.png`,
        });
      }
    }

    const position = (point: MapCenter) => {
      const projected = projectToWorld(point);
      return { left: projected.x - left, top: projected.y - top };
    };

    return { position, tiles };
  }, [center, tileBaseUrl, viewport.height, viewport.width]);

  const onLayout = ({ nativeEvent }: LayoutChangeEvent) => {
    const { width, height } = nativeEvent.layout;
    setViewport((current) =>
      current.width === width && current.height === height ? current : { width, height },
    );
  };

  return (
    <View accessibilityLabel="Mapa com ônibus e pontos próximos" onLayout={onLayout} style={styles.map}>
      {scene?.tiles.map((tile) => (
        <Image
          key={tile.key}
          onError={() => setTileErrors((count) => count + 1)}
          source={{ uri: tile.uri }}
          style={[styles.tile, { left: tile.left, top: tile.top }]}
        />
      ))}

      {scene
        ? stops.map((stop) => {
            const position = scene.position({ latitude: stop.latitude, longitude: stop.longitude });
            return (
              <View
                accessible
                accessibilityLabel={`${stop.stop_name}, ${Math.round(stop.distance_m)} metros`}
                key={`stop-${stop.stop_id}`}
                style={[styles.stopMarker, position]}
              />
            );
          })
        : null}

      {scene
        ? vehicles.map((vehicle) => {
            const quality = presentGpsQuality(vehicle);
            const markerColor =
              quality.status === 'good'
                ? colors.good
                : quality.status === 'degraded'
                  ? colors.degraded
                  : colors.stale;
            const position = scene.position({
              latitude: vehicle.latitude,
              longitude: vehicle.longitude,
            });
            return (
              <View
                accessible
                accessibilityLabel={`Linha ${vehicle.route_id}, veículo ${vehicle.vehicle_id}, ${quality.label}`}
                key={`vehicle-${vehicle.agency_id}-${vehicle.vehicle_id}`}
                style={[styles.vehicleMarker, position, { backgroundColor: markerColor }]}
              />
            );
          })
        : null}

      {tileErrors > 3 ? (
        <View style={styles.tileError}>
          <Text style={styles.tileErrorText}>O mapa-base não carregou. Os dados podem ser atualizados normalmente.</Text>
        </View>
      ) : null}
      <Text style={styles.attribution}>© OpenStreetMap contributors</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  map: { flex: 1, overflow: 'hidden', backgroundColor: '#DCE4EA' },
  tile: { position: 'absolute', width: TILE_SIZE, height: TILE_SIZE },
  stopMarker: {
    position: 'absolute',
    width: 12,
    height: 12,
    marginLeft: -6,
    marginTop: -6,
    borderRadius: 6,
    backgroundColor: colors.stop,
    borderWidth: 2,
    borderColor: colors.surface,
    zIndex: 2,
  },
  vehicleMarker: {
    position: 'absolute',
    width: 18,
    height: 18,
    marginLeft: -9,
    marginTop: -9,
    borderRadius: 5,
    borderWidth: 2,
    borderColor: colors.surface,
    transform: [{ rotate: '45deg' }],
    zIndex: 3,
  },
  attribution: {
    position: 'absolute',
    right: 4,
    bottom: 3,
    color: colors.text,
    backgroundColor: 'rgba(255,255,255,0.82)',
    paddingHorizontal: 4,
    fontSize: 9,
    zIndex: 4,
  },
  tileError: {
    position: 'absolute',
    left: 16,
    right: 16,
    top: 16,
    padding: 12,
    borderRadius: 10,
    backgroundColor: 'rgba(255,255,255,0.94)',
    zIndex: 5,
  },
  tileErrorText: { color: colors.stale, fontSize: 12, lineHeight: 17, textAlign: 'center' },
});

export const osmRasterMapAdapter: MapProviderAdapter = {
  Surface: OsmRasterMapSurface,
  providerName: 'OpenStreetMap raster',
};
