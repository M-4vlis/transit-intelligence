import { useCallback, useEffect, useState } from 'react';

import {
  loadFavoriteRoutes,
  toggleFavoriteRoute,
  type FavoriteRoute,
} from './storage';

export function useFavorites() {
  const [favorites, setFavorites] = useState<FavoriteRoute[]>([]);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    setLoading(true);
    setFavorites(await loadFavoriteRoutes());
    setLoading(false);
  }, []);

  const toggle = useCallback(async (route: FavoriteRoute) => {
    setFavorites(await toggleFavoriteRoute(route));
  }, []);

  useEffect(() => {
    const initialLoad = setTimeout(() => void reload(), 0);
    return () => clearTimeout(initialLoad);
  }, [reload]);

  return { favorites, loading, reload, toggle };
}
