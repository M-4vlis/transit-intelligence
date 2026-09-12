import type { TransitMapProps } from './types';
import { osmRasterMapAdapter } from './osm-raster-map-adapter';

const activeMapAdapter = osmRasterMapAdapter;

export function MapSurface(props: TransitMapProps) {
  return <activeMapAdapter.Surface {...props} />;
}

export const activeMapProviderName = activeMapAdapter.providerName;
