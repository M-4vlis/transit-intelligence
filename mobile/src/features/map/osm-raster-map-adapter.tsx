import { useMemo, useState } from 'react';
import {
  Image,
  PanResponder,
  Pressable,
  StyleSheet,
  Text,
  View,
  type LayoutChangeEvent,
} from 'react-native';

import { getApiBaseUrl } from '@/config/runtime';
import { colors } from '@/constants/theme';
import { presentGpsQuality } from '@/features/quality/gps-quality';

import { selectDecluttered } from './declutter';
import type { MapCenter, MapProviderAdapter, TransitMapProps } from './types';
import {
  centerAfterPan,
  clampZoom,
  DEFAULT_ZOOM,
  MAX_ZOOM,
  MIN_ZOOM,
  projectToWorld,
  TILE_SIZE,
} from './viewport';

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

interface SelectedMarker {
  key: string;
  title: string;
  detail: string;
}

function OsmRasterMapSurface({
  center,
  stops,
  vehicles,
  userLocation,
  onCenterChange,
}: TransitMapProps) {
  const [viewport, setViewport] = useState<ViewportSize>({ width: 0, height: 0 });
  const [tileErrors, setTileErrors] = useState(0);
  const [zoom, setZoom] = useState(DEFAULT_ZOOM);
  const [drag, setDrag] = useState({ x: 0, y: 0 });
  const [selected, setSelected] = useState<SelectedMarker | null>(null);
  const tileBaseUrl = getApiBaseUrl();

  const scene = useMemo(() => {
    if (viewport.width === 0 || viewport.height === 0) {
      return null;
    }

    const centerPixel = projectToWorld(center, zoom);
    const left = centerPixel.x - viewport.width / 2;
    const top = centerPixel.y - viewport.height / 2;
    const minimumTileX = Math.floor(left / TILE_SIZE);
    const maximumTileX = Math.floor((left + viewport.width) / TILE_SIZE);
    const minimumTileY = Math.floor(top / TILE_SIZE);
    const maximumTileY = Math.floor((top + viewport.height) / TILE_SIZE);
    const tileCount = 2 ** zoom;
    const tiles: RasterTile[] = [];

    for (let tileY = minimumTileY; tileY <= maximumTileY; tileY += 1) {
      if (tileY < 0 || tileY >= tileCount) {
        continue;
      }
      for (let tileX = minimumTileX; tileX <= maximumTileX; tileX += 1) {
        const wrappedTileX = ((tileX % tileCount) + tileCount) % tileCount;
        tiles.push({
          key: `${zoom}-${tileX}-${tileY}`,
          left: tileX * TILE_SIZE - left,
          top: tileY * TILE_SIZE - top,
          uri: `${tileBaseUrl}/v1/map/tiles/${zoom}/${wrappedTileX}/${tileY}.png`,
        });
      }
    }

    const position = (point: MapCenter) => {
      const projected = projectToWorld(point, zoom);
      return { left: projected.x - left, top: projected.y - top };
    };

    return { position, tiles };
  }, [center, tileBaseUrl, viewport.height, viewport.width, zoom]);

  const visibleStops = useMemo(
    () =>
      scene
        ? selectDecluttered(
            stops,
            (stop) => scene.position({ latitude: stop.latitude, longitude: stop.longitude }),
            viewport,
            34,
            35,
          )
        : [],
    [scene, stops, viewport],
  );
  const visibleVehicles = useMemo(
    () =>
      scene
        ? selectDecluttered(
            vehicles,
            (vehicle) =>
              scene.position({ latitude: vehicle.latitude, longitude: vehicle.longitude }),
            viewport,
            26,
            60,
          )
        : [],
    [scene, vehicles, viewport],
  );

  const panResponder = useMemo(
    () =>
      PanResponder.create({
        onMoveShouldSetPanResponder: (_, gesture) =>
          Math.abs(gesture.dx) + Math.abs(gesture.dy) > 5,
        onPanResponderMove: (_, gesture) => setDrag({ x: gesture.dx, y: gesture.dy }),
        onPanResponderRelease: (_, gesture) => {
          setDrag({ x: 0, y: 0 });
          setSelected(null);
          onCenterChange?.(centerAfterPan(center, gesture.dx, gesture.dy, zoom));
        },
        onPanResponderTerminate: () => setDrag({ x: 0, y: 0 }),
      }),
    [center, onCenterChange, zoom],
  );

  const onLayout = ({ nativeEvent }: LayoutChangeEvent) => {
    const { width, height } = nativeEvent.layout;
    setViewport((current) =>
      current.width === width && current.height === height ? current : { width, height },
    );
  };

  return (
    <View
      accessibilityLabel="Mapa interativo com ônibus e pontos próximos"
      onLayout={onLayout}
      style={styles.map}
      {...panResponder.panHandlers}>
      <View
        pointerEvents="box-none"
        style={[styles.scene, { transform: [{ translateX: drag.x }, { translateY: drag.y }] }]}>
        {scene?.tiles.map((tile) => (
          <Image
            key={tile.key}
            onError={() => setTileErrors((count) => count + 1)}
            source={{ uri: tile.uri }}
            style={[styles.tile, { left: tile.left, top: tile.top }]}
          />
        ))}

        {visibleStops.map(({ item: stop, left, top }) => (
          <Pressable
            accessibilityLabel={`Ponto ${stop.stop_name}, ${Math.round(stop.distance_m)} metros`}
            accessibilityRole="button"
            hitSlop={6}
            key={`stop-${stop.stop_id}`}
            onPress={() =>
              setSelected({
                key: `stop-${stop.stop_id}`,
                title: stop.stop_name,
                detail: `Ponto de ônibus · ${Math.round(stop.distance_m)} m do centro pesquisado`,
              })
            }
            style={[styles.stopMarker, { left, top }]}
          />
        ))}

        {visibleVehicles.map(({ item: vehicle, left, top }) => {
          const quality = presentGpsQuality(vehicle);
          const markerColor =
            quality.status === 'good'
              ? colors.good
              : quality.status === 'degraded'
                ? colors.degraded
                : colors.stale;
          return (
            <Pressable
              accessibilityLabel={`Linha ${vehicle.route_id}, veículo ${vehicle.vehicle_id}, ${quality.label}`}
              accessibilityRole="button"
              hitSlop={5}
              key={`vehicle-${vehicle.agency_id}-${vehicle.vehicle_id}`}
              onPress={() =>
                setSelected({
                  key: `vehicle-${vehicle.agency_id}-${vehicle.vehicle_id}`,
                  title: `Linha ${vehicle.route_id}`,
                  detail: `Ônibus ${vehicle.vehicle_id} · ${quality.label} · ${quality.detail}`,
                })
              }
              style={[styles.vehicleMarker, { left, top, backgroundColor: markerColor }]}
            />
          );
        })}

        {scene && userLocation ? (
          <View style={[styles.userMarkerHalo, scene.position(userLocation)]}>
            <View style={styles.userMarker} />
          </View>
        ) : null}
      </View>

      <View pointerEvents="none" style={styles.markerSummary}>
        <Text style={styles.markerSummaryText}>
          Exibindo {visibleVehicles.length}/{vehicles.length} ônibus · {visibleStops.length}/
          {stops.length} pontos
        </Text>
      </View>

      <View style={styles.zoomControls}>
        <Pressable
          accessibilityLabel="Aumentar zoom"
          accessibilityRole="button"
          disabled={zoom >= MAX_ZOOM}
          onPress={() => {
            setTileErrors(0);
            setZoom((current) => clampZoom(current + 1));
          }}
          style={styles.zoomButton}>
          <Text style={styles.zoomText}>+</Text>
        </Pressable>
        <Pressable
          accessibilityLabel="Diminuir zoom"
          accessibilityRole="button"
          disabled={zoom <= MIN_ZOOM}
          onPress={() => {
            setTileErrors(0);
            setZoom((current) => clampZoom(current - 1));
          }}
          style={styles.zoomButton}>
          <Text style={styles.zoomText}>−</Text>
        </Pressable>
      </View>

      {selected ? (
        <Pressable
          accessibilityHint="Toque para fechar"
          accessibilityLabel={`${selected.title}. ${selected.detail}`}
          accessibilityRole="button"
          key={selected.key}
          onPress={() => setSelected(null)}
          style={styles.markerCard}>
          <Text style={styles.markerCardTitle}>{selected.title}</Text>
          <Text style={styles.markerCardDetail}>{selected.detail}</Text>
        </Pressable>
      ) : null}

      {tileErrors > 3 ? (
        <View style={styles.tileError}>
          <Text style={styles.tileErrorText}>
            O mapa-base não carregou. Os dados podem ser atualizados normalmente.
          </Text>
        </View>
      ) : null}
      <Text style={styles.attribution}>© OpenStreetMap contributors</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  map: { flex: 1, overflow: 'hidden', backgroundColor: '#DCE4EA' },
  scene: { position: 'absolute', top: 0, right: 0, bottom: 0, left: 0 },
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
  userMarkerHalo: {
    position: 'absolute',
    width: 24,
    height: 24,
    marginLeft: -12,
    marginTop: -12,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(22,112,219,0.22)',
    zIndex: 4,
  },
  userMarker: {
    width: 12,
    height: 12,
    borderRadius: 6,
    backgroundColor: '#1670DB',
    borderWidth: 2,
    borderColor: '#FFFFFF',
  },
  zoomControls: {
    position: 'absolute',
    right: 10,
    top: 10,
    gap: 6,
    zIndex: 6,
  },
  zoomButton: {
    width: 38,
    height: 38,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(255,255,255,0.95)',
    borderWidth: 1,
    borderColor: colors.border,
  },
  zoomText: { color: colors.text, fontSize: 24, fontWeight: '700', lineHeight: 27 },
  markerSummary: {
    position: 'absolute',
    left: 10,
    top: 10,
    maxWidth: '70%',
    paddingHorizontal: 8,
    paddingVertical: 5,
    borderRadius: 8,
    backgroundColor: 'rgba(255,255,255,0.92)',
    zIndex: 5,
  },
  markerSummaryText: { color: colors.text, fontSize: 10, fontWeight: '700' },
  markerCard: {
    position: 'absolute',
    left: 10,
    right: 10,
    bottom: 22,
    padding: 10,
    borderRadius: 12,
    backgroundColor: 'rgba(255,255,255,0.97)',
    borderWidth: 1,
    borderColor: colors.border,
    zIndex: 7,
  },
  markerCardTitle: { color: colors.text, fontSize: 13, fontWeight: '800' },
  markerCardDetail: { color: colors.muted, fontSize: 11, marginTop: 2 },
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
