# Evidência M1.2 — mapa mobile

Data: 2026-09-11

Ambiente de validação: Oracle Ampere A1, `aarch64`, contêiner Node 22 isolado

Produção: stack backend não alterado durante esta validação

## Escopo entregue

- Expo SDK 57, React Native 0.86.3, TypeScript strict e Expo Router;
- identificador neutro `app.transitintelligence.mobile`;
- mapa atrás de `MapProviderAdapter`, atualmente implementado com
  `react-native-maps`;
- cliente tipado para `/v1/routes`, `/v1/stops/nearby`,
  `/v1/vehicles/nearby` e `/v1/routes/{route_id}/vehicles`;
- bloqueio explícito de fontes municipais no runtime mobile e exigência de HTTPS
  fora do desenvolvimento;
- apresentação da idade e qualidade efetiva do GPS;
- favoritos persistidos localmente com AsyncStorage, sem conta.

## Evidências

```text
pnpm run lint       PASS
pnpm run typecheck  PASS
pnpm test           PASS — 4 testes
expo-doctor         PASS — 21/21 checks
expo export android PASS — 1.293 módulos, 27 assets, 2,9 MB
```

O export na máquina ARM64 usou `--no-bytecode`, pois o pacote do compilador
Hermes fornecido pela cadeia Expo contém binário Linux x64. O Metro bundler
concluiu normalmente; o CI x64 executa o export com bytecode habilitado.

## Pendência externa

O build distribuído ainda precisa do valor HTTPS definitivo de
`EXPO_PUBLIC_API_BASE_URL`. O túnel Cloudflare existe, mas a conta ainda não tem
um domínio ativo. Isso permanece no gate M1.0 e não bloqueia a fundação M1.2.
