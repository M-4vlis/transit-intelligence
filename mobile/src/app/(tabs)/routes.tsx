import { useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { transitApi } from '@/api/client';
import type { GtfsRoute } from '@/api/types';
import { RouteCard } from '@/components/route-card';
import { Screen } from '@/components/screen';
import { colors, spacing } from '@/constants/theme';
import { useFavorites } from '@/features/favorites/use-favorites';

export default function RoutesScreen() {
  const [query, setQuery] = useState('');
  const [routes, setRoutes] = useState<GtfsRoute[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { favorites, toggle } = useFavorites();

  async function search() {
    const normalized = query.trim();
    if (!normalized) {
      setError('Digite o número ou o nome de uma linha.');
      return;
    }
    setLoading(true);
    try {
      const page = await transitApi.searchRoutes(normalized);
      setRoutes(page.items);
      setError(page.items.length ? null : 'Nenhuma linha encontrada.');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'A busca não pôde ser concluída.');
    } finally {
      setLoading(false);
    }
  }

  const favoriteIds = new Set(favorites.map((item) => item.routeId));

  return (
    <Screen title="Encontrar linha" subtitle="Busque pelo número, destino ou nome da linha.">
      <View style={styles.searchRow}>
        <TextInput
          accessibilityLabel="Número ou nome da linha"
          autoCapitalize="none"
          onChangeText={setQuery}
          onSubmitEditing={() => void search()}
          placeholder="Ex.: 483 ou Copacabana"
          placeholderTextColor={colors.muted}
          returnKeyType="search"
          style={styles.input}
          value={query}
        />
        <Pressable
          accessibilityRole="button"
          onPress={() => void search()}
          style={({ pressed }) => [styles.searchButton, pressed && styles.pressed]}>
          <Text style={styles.searchButtonText}>Buscar</Text>
        </Pressable>
      </View>

      {loading ? <ActivityIndicator color={colors.primary} /> : null}
      {error ? <Text style={styles.error}>{error}</Text> : null}
      <View style={styles.results}>
        {routes.map((route) => (
          <RouteCard
            key={route.route_id}
            route={route}
            favorite={favoriteIds.has(route.route_id)}
            onToggleFavorite={(item) => void toggle(item)}
          />
        ))}
      </View>
      {!routes.length && !loading && !error ? (
        <View style={styles.empty}>
          <Text style={styles.emptyTitle}>Sua busca começa aqui</Text>
          <Text style={styles.emptyText}>As linhas vêm do catálogo oficial armazenado na nossa API.</Text>
        </View>
      ) : null}
    </Screen>
  );
}

const styles = StyleSheet.create({
  searchRow: { flexDirection: 'row', gap: spacing.sm },
  input: {
    flex: 1,
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: 12,
    paddingHorizontal: spacing.md,
    color: colors.text,
    fontSize: 15,
  },
  searchButton: { backgroundColor: colors.primary, borderRadius: 12, padding: 14, justifyContent: 'center' },
  searchButtonText: { color: '#FFFFFF', fontWeight: '800' },
  results: { gap: spacing.sm },
  error: { color: colors.stale, lineHeight: 20 },
  empty: { alignItems: 'center', paddingVertical: spacing.xl, gap: spacing.sm },
  emptyTitle: { color: colors.text, fontSize: 17, fontWeight: '800' },
  emptyText: { color: colors.muted, textAlign: 'center', lineHeight: 20 },
  pressed: { opacity: 0.7 },
});
