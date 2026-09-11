# M1 — Mapa e ETA básico

## Objetivo

Transformar o Transit Core comprovado no M0 em uma primeira experiência útil:
localizar linhas, paradas e veículos no mapa e apresentar um ETA básico que
degrade com transparência quando o GPS estiver antigo.

## Fatias de entrega

### M1.0 — Borda pública segura

- [x] escolher exposição sem novas portas de entrada na VPS;
- [x] isolar túnel, proxy, API e rede de dados;
- [x] permitir publicamente apenas leituras em `/v1/`;
- [x] bloquear health, readiness, docs e métricas;
- [x] limitar payload, taxa e conexões concorrentes;
- [x] manter logs sem IP do usuário e sem query string;
- [x] adicionar preflight, smoke e runbook;
- [ ] conectar um domínio real ao Cloudflare;
- [ ] executar smoke HTTPS externo e confirmar que a origem não é alcançável
  diretamente;
- [ ] revisar as regras disponíveis de WAF/bot mitigation no plano escolhido.

### M1.1 — Catálogo GTFS no PostGIS

- [x] importar snapshot GTFS identificado por SHA-256;
- [x] versionar agency, routes, stops, trips, stop_times, calendar e shapes;
- [x] fazer troca atômica do snapshot ativo;
- [x] provar idempotência e rollback;
- [x] publicar busca paginada de linhas e paradas próximas.

### M1.2 — Mapa mobile

- [ ] criar Expo + TypeScript strict + Expo Router;
- [ ] definir identificador de pacote provisório e neutro;
- [ ] implementar adapter de mapas sem acoplamento ao fornecedor;
- [ ] consumir somente a API própria;
- [ ] exibir idade e estado de qualidade do GPS;
- [ ] armazenar favoritos localmente, sem cadastro obrigatório.

### M1.3 — ETA V0

- [ ] casar veículo, viagem, shape e próximas paradas;
- [ ] calcular ETA geométrico/operacional com limites explícitos;
- [ ] usar histórico agregado por trecho/faixa horária quando disponível;
- [ ] retornar idade da observação e motivo de indisponibilidade;
- [ ] medir MAE e erro P50/P90 em replay histórico;
- [ ] impedir que um ETA sem evidência seja apresentado como confiável.

## Arquitetura de borda escolhida

```text
App / Internet
      |
      v
Cloudflare (TLS/WAF)
      |
      | túnel iniciado de dentro para fora
      v
cloudflared -- rede tunnel
      |
      v
Nginx policy proxy -- redes tunnel + api-edge
      |
      v
FastAPI -- redes api-edge + data
      |
      +--> Valkey / PostGIS -- rede data
```

`cloudflared` não compartilha rede com a API ou com os dados. O proxy não
compartilha a rede de dados. Nenhum serviço de borda publica porta no host.

## Definição de pronto do M1

O M1 termina quando um build mobile de teste consegue pesquisar uma linha,
visualizar veículos/paradas no mapa e consultar ETA V0 através de HTTPS, enquanto
os testes demonstram isolamento da origem, limites de abuso, dados atuais e
degradação segura.
