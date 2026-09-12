export type QualityStatus = 'good' | 'degraded' | 'stale' | 'invalid';

export interface VehiclePosition {
  agency_id: string;
  vehicle_id: string;
  route_id: string;
  trip_id: string | null;
  shape_id: string | null;
  latitude: number;
  longitude: number;
  speed_mps: number | null;
  bearing_deg: number | null;
  observed_at: string;
  received_at: string;
  source: string;
  quality_status: QualityStatus;
  quality_score: number;
}

export interface GtfsRoute {
  snapshot_id: string;
  route_id: string;
  agency_id: string | null;
  route_short_name: string | null;
  route_long_name: string | null;
  route_desc: string | null;
  route_type: number;
  route_color: string | null;
  route_text_color: string | null;
}

export interface NearbyStop {
  snapshot_id: string;
  stop_id: string;
  stop_code: string | null;
  stop_name: string;
  stop_desc: string | null;
  latitude: number;
  longitude: number;
  location_type: number | null;
  parent_station: string | null;
  wheelchair_boarding: number | null;
  distance_m: number;
}

export interface Page<T> {
  items: T[];
  limit: number;
  offset: number;
  total: number;
}
