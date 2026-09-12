export function presentRouteLabel(routeId: string): string {
  const rioNumericId = /^[A-Za-z](\d{4})/.exec(routeId);
  if (!rioNumericId) {
    return routeId;
  }
  return String(Number(rioNumericId[1]));
}

export function uniqueRouteIds(routeIds: string[]): string[] {
  return [...new Set(routeIds)].sort((left, right) =>
    presentRouteLabel(left).localeCompare(presentRouteLabel(right), 'pt-BR', { numeric: true }),
  );
}
