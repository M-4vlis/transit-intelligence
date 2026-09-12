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

export type EtaUnavailableReason =
  | 'stale_position'
  | 'insufficient_speed_evidence'
  | 'distance_out_of_range';

export interface EtaEvidence {
  method:
    | 'vehicle_recent_speed'
    | 'historical_segment_time_band'
    | 'route_shape_recent_speed';
  confidence: 'experimental';
  sample_count: number;
  window_seconds: number;
  speed_p25_mps: number;
  speed_median_mps: number;
  speed_p75_mps: number;
}

export interface UpcomingStop {
  stop_id: string;
  stop_name: string;
  latitude: number;
  longitude: number;
  stop_sequence: number;
  shape_dist_traveled: number;
  shape_distance_ahead: number;
  estimated_arrival_at: string | null;
  eta_seconds: number | null;
  eta_lower_seconds: number | null;
  eta_upper_seconds: number | null;
  eta_unavailable_reason: EtaUnavailableReason | null;
}

export interface VehicleJourneyMatch {
  available: boolean;
  unavailable_reason:
    | 'missing_shape_id'
    | 'route_shape_not_found'
    | 'shape_projection_failed'
    | 'vehicle_off_shape'
    | 'no_upcoming_stops'
    | null;
  snapshot_id: string | null;
  vehicle_id: string;
  route_id: string;
  source_trip_id: string | null;
  matched_trip_id: string | null;
  shape_id: string | null;
  match_method: 'exact_trip' | 'route_shape_pattern' | null;
  observed_at: string;
  evaluated_at: string | null;
  position_age_seconds: number | null;
  projected_shape_dist_traveled: number | null;
  projection_distance_m: number | null;
  eta_evidence: EtaEvidence | null;
  eta_unavailable_reason: EtaUnavailableReason | null;
  upcoming_stops: UpcomingStop[];
}
