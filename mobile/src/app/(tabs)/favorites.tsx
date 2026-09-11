import { useCallback } from 'react';
import { useFocusEffect } from 'expo-router';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';

import { RouteCard } from '@/components/route-card';
import { Screen } from '@/components/screen';
import { colors, spacing } from '@/constants/theme';
import { useFavorites } from '@/features/favorites/use-favorites';

export default function FavoritesScreen() {
  const { favorites, loading, reload, toggle } = useFavorites();

  useFocusEffect(
    useCallback(() => {
      void reload();
    }, [reload]),
  );

  return (
    <Screen title="Linhas favoritas" subtitle="Salvas somente neste aparelho, sem exigir cadastro.">
      {loading ? <ActivityIndicator color={colors.primary} /> : null}
      {!loading && favorites.length === 0 ? (
        <View style={styles.empty}>
          <Text style={styles.emptyTitle}>Nenhuma linha salva</Text>
          <Text style={styles.emptyText}>Use a aba Linhas para guardar as que você acompanha.</Text>
        </View>
      ) : null}
      <View style={styles.list}>
        {favorites.map((route) => (
          <RouteCard
            key={route.routeId}
            route={route}
            favorite
            onToggleFavorite={(item) => void toggle(item)}
          />
        ))}
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  list: { gap: spacing.sm },
  empty: { alignItems: 'center', paddingVertical: spacing.xl, gap: spacing.sm },
  emptyTitle: { color: colors.text, fontSize: 17, fontWeight: '800' },
  emptyText: { color: colors.muted, textAlign: 'center', lineHeight: 20 },
});
