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

- [x] criar Expo + TypeScript strict + Expo Router;
- [x] definir identificador de pacote provisório e neutro;
- [x] implementar adapter de mapas sem acoplamento ao fornecedor;
- [x] consumir somente a API própria;
- [x] exibir idade e estado de qualidade do GPS;
- [x] armazenar favoritos localmente, sem cadastro obrigatório.

### M1.3 — ETA V0

- [x] preservar `shape_id` do GPS e `shape_dist_traveled` do GTFS nos contratos
  e armazenamentos novos;
- [x] tornar o avanço da janela realtime dependente da persistência completa,
  permitindo repetição integral após falha;
- [x] reidratar a distância das paradas do snapshot ativo ou derivá-la por
  projeção validada sobre o shape;
- [x] casar veículo, viagem, shape e próximas paradas;
- [x] calcular ETA geométrico/operacional com limites explícitos;
- [x] usar histórico agregado por trecho/faixa horária quando disponível;
- [x] retornar idade da observação e motivo de indisponibilidade;
- [x] medir MAE e erro P50/P90 em replay histórico;
- [x] impedir que um ETA sem evidência seja apresentado como confiável.

### M1.4 — Refinamento do mapa após o ETA V0

- [x] solicitar localização somente por ação do usuário e centralizar o mapa
  nela, mantendo uma posição inicial segura quando a permissão for negada;
- [x] permitir mover, ampliar e recentralizar o mapa, com atualização explícita
  da área visível;
- [x] diferenciar visualmente paradas e veículos com ícones, legenda acessível e
  identificação ao toque;
- [x] reduzir sobreposição de marcadores por filtro de linha e agrupamento;
- [x] validar legibilidade, gestos e estados de permissão em aparelho real.

Esses itens foram registrados após o primeiro teste em aparelho da v0.1.2. O
mapa funcional atual permanece deliberadamente simples enquanto o ETA V0 prova
o vínculo entre GPS e GTFS.

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
Nginx policy proxy -- redes tunnel + api-edge + egress restrito para tiles
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
