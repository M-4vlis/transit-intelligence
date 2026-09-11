import { useMemo, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';

import { Screen } from '@/components/screen';
import { colors, spacing } from '@/constants/theme';
import { MapSurface } from '@/features/map/map-surface';
import type { MapCenter } from '@/features/map/types';
import { useNearbyTransit } from '@/features/map/use-nearby-transit';
import { presentGpsQuality } from '@/features/quality/gps-quality';

const CENTRAL_RIO: MapCenter = { latitude: -22.904, longitude: -43.191 };

export default function MapScreen() {
  const [center, setCenter] = useState(CENTRAL_RIO);
  const { stops, vehicles, loading, error, refresh } = useNearbyTransit(center);
  const qualityCounts = useMemo(
    () =>
      vehicles.reduce(
        (counts, vehicle) => {
          counts[presentGpsQuality(vehicle).status] += 1;
          return counts;
        },
        { good: 0, degraded: 0, stale: 0, invalid: 0 },
      ),
    [vehicles],
  );

  return (
    <Screen
      title="Mapa ao vivo"
      subtitle="Ônibus e pontos próximos ao centro do mapa."
      scroll={false}>
      <View style={styles.summaryRow}>
        <Text style={styles.summary}>{vehicles.length} ônibus</Text>
        <Text style={styles.summary}>{stops.length} pontos</Text>
        <View style={styles.qualityPill}>
          <Text style={styles.qualityText}>{qualityCounts.good} com GPS atual</Text>
        </View>
      </View>

      <View style={styles.mapCard}>
        <MapSurface center={CENTRAL_RIO} stops={stops} vehicles={vehicles} onCenterChange={setCenter} />
        {loading ? (
          <View style={styles.loadingOverlay}>
            <ActivityIndicator color={colors.primary} />
            <Text style={styles.loadingText}>Atualizando...</Text>
          </View>
        ) : null}
      </View>

      {error ? <Text style={styles.error}>{error}</Text> : null}
      <Pressable
        accessibilityRole="button"
        onPress={() => void refresh()}
        style={({ pressed }) => [styles.button, pressed && styles.pressed]}>
        <Text style={styles.buttonText}>Atualizar esta área</Text>
      </Pressable>
      <Text style={styles.legend}>Azul: ponto · Verde/laranja/vermelho: qualidade do GPS do ônibus</Text>
    </Screen>
  );
}

const styles = StyleSheet.create({
  summaryRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, flexWrap: 'wrap' },
  summary: { color: colors.text, fontSize: 13, fontWeight: '700' },
  qualityPill: { backgroundColor: colors.primarySoft, borderRadius: 20, padding: spacing.sm },
  qualityText: { color: colors.good, fontSize: 12, fontWeight: '700' },
  mapCard: {
    flex: 1,
    minHeight: 360,
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
  error: { color: colors.stale, fontSize: 13, lineHeight: 18 },
  button: { backgroundColor: colors.primary, borderRadius: 12, alignItems: 'center', padding: 13 },
  buttonText: { color: '#FFFFFF', fontSize: 15, fontWeight: '800' },
  pressed: { opacity: 0.7 },
  legend: { color: colors.muted, fontSize: 11, textAlign: 'center' },
});
