const FORBIDDEN_SOURCE_HOSTS = new Set([
  'dados.mobilidade.rio',
  'jeap.rio.rj.gov.br',
]);

export function getApiBaseUrl(): string {
  const configured = process.env.EXPO_PUBLIC_API_BASE_URL?.trim();
  if (!configured) {
    throw new Error('Defina EXPO_PUBLIC_API_BASE_URL para conectar o aplicativo.');
  }

  let url: URL;
  try {
    url = new URL(configured);
  } catch {
    throw new Error('EXPO_PUBLIC_API_BASE_URL não é uma URL válida.');
  }

  if (FORBIDDEN_SOURCE_HOSTS.has(url.hostname.toLowerCase())) {
    throw new Error('O aplicativo deve usar somente a API do Transit Intelligence.');
  }
  if (!__DEV__ && url.protocol !== 'https:') {
    throw new Error('A API precisa usar HTTPS fora do desenvolvimento local.');
  }
  if (!['http:', 'https:'].includes(url.protocol)) {
    throw new Error('A API precisa usar HTTP ou HTTPS.');
  }

  return url.toString().replace(/\/$/, '');
}
