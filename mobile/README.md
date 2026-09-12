# Aplicativo móvel

Base do M1.2 em Expo SDK 57, React Native, TypeScript strict e Expo Router.

## Decisões já aplicadas

- identificador neutro: `app.transitintelligence.mobile`;
- toda leitura de transporte passa pela API própria;
- acesso direto às fontes municipais é recusado pela configuração do app;
- mapas ficam atrás de `MapProviderAdapter`;
- idade e qualidade do GPS são mostradas ao usuário;
- linhas favoritas ficam apenas no aparelho, sem conta obrigatória.
- localização é solicitada somente por ação do usuário;
- o mapa permite arrastar, ampliar, recentralizar e atualizar a área consultada;
- marcadores podem ser identificados ao toque e são reduzidos por célula visual;
- ônibus próximos podem ser filtrados por linha;
- tocar em um ônibus consulta próximas paradas e ETA V0 experimental pela API.

## Executar

```bash
cp .env.example .env.local
corepack enable
pnpm install
pnpm start
```

Defina `EXPO_PUBLIC_API_BASE_URL`. Em desenvolvimento, HTTP local é aceito. Fora do
modo de desenvolvimento, somente HTTPS é permitido.

## Verificar

```bash
pnpm run lint
pnpm run typecheck
pnpm test
```

Builds de teste podem usar uma URL HTTPS temporária do Cloudflare Quick Tunnel.
O endereço público definitivo ainda depende de conectar um domínio ao túnel
Cloudflare já provisionado. Essa pendência não altera a arquitetura do app.
