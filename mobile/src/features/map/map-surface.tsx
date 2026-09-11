import type { TransitMapProps } from './types';
import { reactNativeMapsAdapter } from './react-native-maps-adapter';

const activeMapAdapter = reactNativeMapsAdapter;

export function MapSurface(props: TransitMapProps) {
  return <activeMapAdapter.Surface {...props} />;
}

export const activeMapProviderName = activeMapAdapter.providerName;
