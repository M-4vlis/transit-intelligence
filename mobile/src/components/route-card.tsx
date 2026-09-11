import { Pressable, StyleSheet, Text, View } from 'react-native';

import type { GtfsRoute } from '@/api/types';
import { colors, spacing } from '@/constants/theme';
import { routeToFavorite, type FavoriteRoute } from '@/features/favorites/storage';

interface RouteCardProps {
  route: GtfsRoute | FavoriteRoute;
  favorite: boolean;
  onToggleFavorite: (route: FavoriteRoute) => void;
}

function normalizeRoute(route: GtfsRoute | FavoriteRoute): FavoriteRoute {
  return 'routeId' in route ? route : routeToFavorite(route);
}

export function RouteCard({ route, favorite, onToggleFavorite }: RouteCardProps) {
  const item = normalizeRoute(route);
  return (
    <View style={styles.card}>
      <View style={styles.routeBadge}>
        <Text style={styles.routeBadgeText}>{item.shortName}</Text>
      </View>
      <View style={styles.details}>
        <Text style={styles.name}>{item.longName}</Text>
        <Text style={styles.code}>Linha {item.routeId}</Text>
      </View>
      <Pressable
        accessibilityLabel={favorite ? 'Remover dos favoritos' : 'Adicionar aos favoritos'}
        onPress={() => onToggleFavorite(item)}
        style={({ pressed }) => [styles.favorite, pressed && styles.pressed]}>
        <Text style={[styles.favoriteText, favorite && styles.favoriteTextActive]}>
          {favorite ? 'Salva' : 'Salvar'}
        </Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: 16,
    padding: spacing.md,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
  },
  routeBadge: {
    minWidth: 58,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.sm,
    borderRadius: 10,
    backgroundColor: colors.primarySoft,
    alignItems: 'center',
  },
  routeBadgeText: { color: colors.primary, fontSize: 16, fontWeight: '800' },
  details: { flex: 1, gap: 3 },
  name: { color: colors.text, fontSize: 15, lineHeight: 20, fontWeight: '700' },
  code: { color: colors.muted, fontSize: 12 },
  favorite: { paddingHorizontal: spacing.sm, paddingVertical: spacing.sm },
  favoriteText: { color: colors.primary, fontSize: 13, fontWeight: '700' },
  favoriteTextActive: { color: colors.good },
  pressed: { opacity: 0.55 },
});
