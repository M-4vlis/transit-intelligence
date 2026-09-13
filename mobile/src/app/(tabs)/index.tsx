import * as Location from 'expo-location';
import { useMemo, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { Screen } from '@/components/screen';
import { colors, spacing } from '@/constants/theme';
import { presentEta, presentJourneyUnavailable } from '@/features/eta/presentation';
import { useVehicleEta } from '@/features/eta/use-vehicle-eta';
import { MapSurface } from '@/features/map/map-surface';
import type { MapCenter } from '@/features/map/types';
import { presentRouteLabel, uniqueRouteLabels } from '@/features/map/route-filter';
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
  const [selectedRouteLabel, setSelectedRouteLabel] = useState<string | null>(null);
  const eta = useVehicleEta();
  const { stops, vehicles, loading, error, refresh } = useNearbyTransit(loadedCenter);
  const areaMoved = centersDiffer(center, loadedCenter);
  const routeLabels = useMemo(
    () => uniqueRouteLabels(vehicles.map((vehicle) => vehicle.route_id)),
    [vehicles],
  );
  const activeRouteLabel =
    selectedRouteLabel && routeLabels.includes(selectedRouteLabel) ? selectedRouteLabel : null;
  const displayedVehicles = useMemo(
    () =>
      activeRouteLabel
        ? vehicles.filter(
            (vehicle) => presentRouteLabel(vehicle.route_id) === activeRouteLabel,
          )
        : vehicles,
    [activeRouteLabel, vehicles],
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
          accessibilityState={{ selected: activeRouteLabel === null }}
          onPress={() => setSelectedRouteLabel(null)}
          style={[styles.filterChip, activeRouteLabel === null && styles.filterChipSelected]}>
          <Text
            style={[
              styles.filterChipText,
              activeRouteLabel === null && styles.filterChipTextSelected,
            ]}>
            Todas
          </Text>
        </Pressable>
        {routeLabels.map((routeLabel) => {
          const selected = routeLabel === activeRouteLabel;
          return (
            <Pressable
              accessibilityLabel={`Filtrar linha ${routeLabel}`}
              accessibilityRole="button"
              accessibilityState={{ selected }}
              key={routeLabel}
              onPress={() => setSelectedRouteLabel(selected ? null : routeLabel)}
              style={[styles.filterChip, selected && styles.filterChipSelected]}>
              <Text style={[styles.filterChipText, selected && styles.filterChipTextSelected]}>
                {routeLabel}
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
          onVehiclePress={(vehicle) => void eta.load(vehicle)}
        />
        {loading ? (
          <View style={styles.loadingOverlay}>
            <ActivityIndicator color={colors.primary} />
            <Text style={styles.loadingText}>Atualizando...</Text>
          </View>
        ) : null}
        {eta.vehicle ? (
          <View style={styles.etaCard}>
            <View style={styles.etaHeader}>
              <View style={styles.etaHeading}>
                <Text style={styles.etaTitle}>
                  Linha {presentRouteLabel(eta.vehicle.route_id)} · ônibus {eta.vehicle.vehicle_id}
                </Text>
                <Text style={styles.etaCaption}>Próximas paradas · ETA experimental</Text>
              </View>
              <Pressable
                accessibilityLabel="Fechar previsão"
                accessibilityRole="button"
                hitSlop={8}
                onPress={eta.clear}>
                <Text style={styles.etaClose}>×</Text>
              </Pressable>
            </View>
            {eta.loading ? (
              <View style={styles.etaLoading}>
                <ActivityIndicator color={colors.primary} size="small" />
                <Text style={styles.etaCaption}>Calculando com o GPS atual...</Text>
              </View>
            ) : null}
            {eta.error ? <Text style={styles.etaError}>{eta.error}</Text> : null}
            {eta.journey && !eta.journey.available ? (
              <Text style={styles.etaError}>
                ETA indisponível: {presentJourneyUnavailable(eta.journey.unavailable_reason)}.
              </Text>
            ) : null}
            {eta.journey?.available
              ? eta.journey.upcoming_stops.slice(0, 3).map((stop) => {
                  const prediction = presentEta(stop);
                  return (
                    <View key={stop.stop_id} style={styles.etaStopRow}>
                      <Text numberOfLines={1} style={styles.etaStopName}>
                        {stop.stop_name}
                      </Text>
                      <View style={styles.etaValueBlock}>
                        <Text style={styles.etaValue}>{prediction.eta}</Text>
                        <Text style={styles.etaDetail}>{prediction.detail}</Text>
                      </View>
                    </View>
                  );
                })
              : null}
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
  etaCard: {
    position: 'absolute',
    left: 8,
    right: 8,
    bottom: 8,
    padding: 11,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: 'rgba(255,255,255,0.98)',
    zIndex: 20,
  },
  etaHeader: { flexDirection: 'row', alignItems: 'flex-start', gap: spacing.sm },
  etaHeading: { flex: 1 },
  etaTitle: { color: colors.text, fontSize: 13, fontWeight: '800' },
  etaCaption: { color: colors.muted, fontSize: 10, marginTop: 1 },
  etaClose: { color: colors.muted, fontSize: 24, lineHeight: 24 },
  etaLoading: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginTop: 8 },
  etaError: { color: colors.stale, fontSize: 11, lineHeight: 15, marginTop: 7 },
  etaStopRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    paddingTop: 6,
    marginTop: 6,
  },
  etaStopName: { flex: 1, color: colors.text, fontSize: 11, fontWeight: '700' },
  etaValueBlock: { alignItems: 'flex-end', maxWidth: '48%' },
  etaValue: { color: colors.primary, fontSize: 12, fontWeight: '800' },
  etaDetail: { color: colors.muted, fontSize: 9, textAlign: 'right' },
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
