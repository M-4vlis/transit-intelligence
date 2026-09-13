export function presentRouteLabel(routeId: string): string {
  const rioNumericId = /^[A-Za-z](\d{4})/.exec(routeId);
  if (!rioNumericId) {
    return routeId;
  }
  return String(Number(rioNumericId[1]));
}

export function uniqueRouteLabels(routeIds: string[]): string[] {
  return [...new Set(routeIds.map(presentRouteLabel))].sort((left, right) =>
    left.localeCompare(right, 'pt-BR', { numeric: true }),
  );
}
