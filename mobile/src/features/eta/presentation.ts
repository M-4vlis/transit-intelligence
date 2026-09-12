import type { UpcomingStop, VehicleJourneyMatch } from '@/api/types';

const JOURNEY_REASON: Record<NonNullable<VehicleJourneyMatch['unavailable_reason']>, string> = {
  missing_shape_id: 'o veículo ainda não informou seu trajeto',
  route_shape_not_found: 'o trajeto desta linha não foi localizado',
  shape_projection_failed: 'não foi possível posicionar o veículo no trajeto',
  vehicle_off_shape: 'o veículo está distante do trajeto esperado',
  no_upcoming_stops: 'não há próximas paradas identificadas',
};

const ETA_REASON = {
  stale_position: 'GPS antigo',
  insufficient_speed_evidence: 'velocidade ainda insuficiente',
  distance_out_of_range: 'parada fora do alcance da estimativa',
} as const;

function minutes(seconds: number): number {
  return Math.max(1, Math.ceil(seconds / 60));
}

export function presentEta(stop: UpcomingStop): { eta: string; detail: string } {
  if (stop.eta_seconds === null) {
    return {
      eta: 'Sem ETA',
      detail: stop.eta_unavailable_reason
        ? ETA_REASON[stop.eta_unavailable_reason]
        : 'estimativa indisponível',
    };
  }

  const eta = stop.eta_seconds <= 30 ? 'Chegando' : `${minutes(stop.eta_seconds)} min`;
  const lower = stop.eta_lower_seconds;
  const upper = stop.eta_upper_seconds;
  const detail =
    lower !== null && upper !== null
      ? `faixa experimental ${Math.floor(lower / 60)}–${minutes(upper)} min`
      : 'estimativa experimental';
  return { eta, detail };
}

export function presentJourneyUnavailable(
  reason: VehicleJourneyMatch['unavailable_reason'],
): string {
  return reason ? JOURNEY_REASON[reason] : 'não foi possível calcular a viagem agora';
}
