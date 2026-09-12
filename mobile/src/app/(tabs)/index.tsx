import * as Location from 'expo-location';
import { useMemo, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { Screen } from '@/components/screen';
import { colors, spacing } from '@/constants/theme';
import { MapSurface } from '@/features/map/map-surface';
import type { MapCenter } from '@/features/map/types';
import { presentRouteLabel, uniqueRouteIds } from '@/features/map/route-filter';
import { useNearbyTransit } from '@/features/map/use-nearby-transit';
import { presentGpsQuality } from '@/features/quality/gps-quality';

const CENTRAL_RIO: MapCenter = { latitude: -22.904, longitude: -43.191 };

function centersDiffer(left: MapCenter, right: MapCenter) {
  return (
    Math.abs(left.latitude - right.latitude) > 0.00001 ||
    Math.abs(left.longitude - right.longitude) > 0.00001
  );
}

export default function MapScreen() {
  const [center, setCenter] = useState(CENTRAL_RIO);
  const [loadedCenter, setLoadedCenter] = useState(CENTRAL_RIO);
  const [userLocation, setUserLocation] = useState<MapCenter | null>(null);
  const [locating, setLocating] = useState(false);
  const [locationError, setLocationError] = useState<string | null>(null);
  const [selectedRouteId, setSelectedRouteId] = useState<string | null>(null);
  const { stops, vehicles, loading, error, refresh } = useNearbyTransit(loadedCenter);
  const areaMoved = centersDiffer(center, loadedCenter);
  const routeIds = useMemo(
    () => uniqueRouteIds(vehicles.map((vehicle) => vehicle.route_id)),
    [vehicles],
  );
  const activeRouteId =
    selectedRouteId && routeIds.includes(selectedRouteId) ? selectedRouteId : null;
  const displayedVehicles = useMemo(
    () =>
      activeRouteId
        ? vehicles.filter((vehicle) => vehicle.route_id === activeRouteId)
        : vehicles,
    [activeRouteId, vehicles],
  );
  const qualityCounts = useMemo(
    () =>
      displayedVehicles.reduce(
        (counts, vehicle) => {
          counts[presentGpsQuality(vehicle).status] += 1;
          return counts;
        },
        { good: 0, degraded: 0, stale: 0, invalid: 0 },
      ),
    [displayedVehicles],
  );

  const updateVisibleArea = () => {
    if (areaMoved) {
      setLoadedCenter(center);
    } else {
      void refresh();
    }
  };

  const centerOnUser = async () => {
    setLocating(true);
    setLocationError(null);
    try {
      const permission = await Location.requestForegroundPermissionsAsync();
      if (!permission.granted) {
        setLocationError('Localização não autorizada. O mapa continuará no centro do Rio.');
        return;
      }
      const current = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.Balanced,
      });
      const nextCenter = {
        latitude: current.coords.latitude,
        longitude: current.coords.longitude,
      };
      setUserLocation(nextCenter);
      setCenter(nextCenter);
      setLoadedCenter(nextCenter);
    } catch {
      setLocationError('Não foi possível obter sua localização agora.');
    } finally {
      setLocating(false);
    }
  };

  return (
    <Screen
      title="Mapa ao vivo"
      subtitle="Arraste o mapa ou use sua localização para explorar outra área."
      scroll={false}>
      <View style={styles.summaryRow}>
        <Text style={styles.summary}>{displayedVehicles.length} ônibus</Text>
        <Text style={styles.summary}>{stops.length} pontos</Text>
        <View style={styles.qualityPill}>
          <Text style={styles.qualityText}>{qualityCounts.good} com GPS atual</Text>
        </View>
      </View>

      <ScrollView
        accessibilityLabel="Filtro de linhas no mapa"
        contentContainerStyle={styles.filterRow}
        horizontal
        showsHorizontalScrollIndicator={false}>
        <Pressable
          accessibilityRole="button"
          accessibilityState={{ selected: activeRouteId === null }}
          onPress={() => setSelectedRouteId(null)}
          style={[styles.filterChip, activeRouteId === null && styles.filterChipSelected]}>
          <Text
            style={[
              styles.filterChipText,
              activeRouteId === null && styles.filterChipTextSelected,
            ]}>
            Todas
          </Text>
        </Pressable>
        {routeIds.map((routeId) => {
          const selected = routeId === activeRouteId;
          return (
            <Pressable
              accessibilityLabel={`Filtrar linha ${presentRouteLabel(routeId)}`}
              accessibilityRole="button"
              accessibilityState={{ selected }}
              key={routeId}
              onPress={() => setSelectedRouteId(selected ? null : routeId)}
              style={[styles.filterChip, selected && styles.filterChipSelected]}>
              <Text style={[styles.filterChipText, selected && styles.filterChipTextSelected]}>
                {presentRouteLabel(routeId)}
              </Text>
            </Pressable>
          );
        })}
      </ScrollView>

      <View style={styles.mapCard}>
        <MapSurface
          center={center}
          stops={stops}
          userLocation={userLocation}
          vehicles={displayedVehicles}
          onCenterChange={setCenter}
        />
        {loading ? (
          <View style={styles.loadingOverlay}>
            <ActivityIndicator color={colors.primary} />
            <Text style={styles.loadingText}>Atualizando...</Text>
          </View>
        ) : null}
      </View>

      {areaMoved ? <Text style={styles.notice}>Área movida. Atualize para buscar os dados daqui.</Text> : null}
      {error ? <Text style={styles.error}>{error}</Text> : null}
      {locationError ? <Text style={styles.error}>{locationError}</Text> : null}
      <View style={styles.actionRow}>
        <Pressable
          accessibilityRole="button"
          disabled={locating}
          onPress={() => void centerOnUser()}
          style={({ pressed }) => [styles.secondaryButton, pressed && styles.pressed]}>
          {locating ? (
            <ActivityIndicator color={colors.primary} />
          ) : (
            <Text style={styles.secondaryButtonText}>Minha localização</Text>
          )}
        </Pressable>
        <Pressable
          accessibilityRole="button"
          onPress={updateVisibleArea}
          style={({ pressed }) => [styles.button, pressed && styles.pressed]}>
          <Text style={styles.buttonText}>Atualizar área</Text>
        </Pressable>
      </View>
      <Text style={styles.legend}>
        Azul: ponto · Losango: ônibus · Círculo azul: sua localização
      </Text>
    </Screen>
  );
}

const styles = StyleSheet.create({
  summaryRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, flexWrap: 'wrap' },
  summary: { color: colors.text, fontSize: 13, fontWeight: '700' },
  qualityPill: { backgroundColor: colors.primarySoft, borderRadius: 20, padding: spacing.sm },
  qualityText: { color: colors.good, fontSize: 12, fontWeight: '700' },
  filterRow: { gap: 7, paddingVertical: 1 },
  filterChip: {
    minWidth: 54,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  filterChipSelected: { borderColor: colors.primary, backgroundColor: colors.primary },
  filterChipText: { color: colors.text, fontSize: 12, fontWeight: '700' },
  filterChipTextSelected: { color: '#FFFFFF' },
  mapCard: {
    flex: 1,
    minHeight: 340,
    borderRadius: 20,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  loadingOverlay: {
    position: 'absolute',
    top: spacing.md,
    alignSelf: 'center',
    flexDirection: 'row',
    gap: spacing.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: 20,
    backgroundColor: colors.surface,
  },
  loadingText: { color: colors.text, fontSize: 13 },
  notice: { color: colors.primary, fontSize: 12, textAlign: 'center' },
  error: { color: colors.stale, fontSize: 13, lineHeight: 18 },
  actionRow: { flexDirection: 'row', gap: spacing.sm },
  button: {
    flex: 1,
    backgroundColor: colors.primary,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 13,
  },
  buttonText: { color: '#FFFFFF', fontSize: 14, fontWeight: '800' },
  secondaryButton: {
    flex: 1,
    minHeight: 45,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 10,
    backgroundColor: colors.surface,
  },
  secondaryButtonText: { color: colors.primary, fontSize: 13, fontWeight: '800' },
  pressed: { opacity: 0.7 },
  legend: { color: colors.muted, fontSize: 11, textAlign: 'center' },
});
