# M0 — Transit Core

## Objetivo
Criar o primeiro núcleo operacional capaz de receber dados de mobilidade do Rio, normalizá-los, avaliar sua confiabilidade, persistir estado recente e disponibilizá-lo por uma API própria.

## Status em 03/09/2026 — v0.7

### M0.1 — Contratos — CONCLUÍDO
- `VehiclePosition` canônico;
- DTO tolerante da fonte Rio;
- contrato `TransitRealtimeAdapter`;
- erros de fonte classificados;
- fingerprint determinístico para idempotência;
- fingerprint de schema observado por lote.

### M0.2 — Quality Engine V0 — CONCLUÍDO
Regras determinísticas para timestamp futuro, GPS stale e velocidade implausível; score 0–1 e motivos explicáveis.

### M0.3 — Ingestão — IMPLEMENTADO / AGUARDA PRIMEIRO CANARY LIVE
- endpoint oficial configurado;
- timeout, retry, exponential backoff + jitter;
- circuit breaker;
- limite de resposta;
- HTTPS + source-host allowlist;
- validação de schema e quarentena;
- deduplicação;
- lease distribuído single-active-collector;
- métricas Prometheus específicas do worker;
- registro de schema fingerprint e campos observados;
- canary independente agendado a cada 6 horas;
- tolerância a mudanças numéricas/string em identificadores e epoch em segundos/milisegundos.

### M0.4 — Persistência — IMPLEMENTADO / AGUARDA INTEGRAÇÃO
- Valkey para hot state com TTL;
- PostgreSQL + PostGIS;
- partições diárias sob demanda;
- índices temporal, rota, veículo e geoespacial;
- quarentena persistente;
- writer Parquet ZSTD em streaming;
- manifests para arquivo frio;
- writer S3-compatible genérico para OCI/R2;
- SHA-256 local e verificação remota integral;
- retenção fail-closed com revalidação remota imediatamente antes do `DROP PARTITION`;
- retenção exige paridade de contagem hot/archive e bloqueia partições que contenham outra fonte;
- escrita e retenção compartilham advisory lock por partição, fechando corrida com telemetria tardia;
- estado Valkey monotônico por `observed_at`, impedindo GPS atrasado de sobrescrever posição nova.

### M0.5 — API — IMPLEMENTADO / AGUARDA INTEGRAÇÃO
- `/health/live`;
- `/health/ready`;
- `/metrics` da API;
- `/v1/routes/{route_id}/vehicles`;
- `/v1/vehicles/nearby`.

## Próximas ações do M0
1. aguardar a recuperação do endpoint realtime oficial e capturar a primeira fixture live aprovada;
2. confirmar persistência, cache e fingerprint com dados reais;
3. deixar o watcher concluir o soak válido de pelo menos 24 horas;
4. arquivar uma partição não vazia no OCI Object Storage e repetir o restore check;
5. criar o repositório remoto e ativar o CI/canary fora do ciclo de deployment;
6. somente então revisar retenção destrutiva e declarar M0 operacionalmente concluído.

## Definition of Done
M0 termina quando mantivermos coleta contínua real, reiniciarmos serviços sem perda lógica, consultarmos posições pela nossa API, arquivarmos o histórico com verificação e medirmos qualidade/falhas da fonte com observabilidade suficiente para operação.

## v0.6 — Gate operacional / Oracle ARM64

A infraestrutura de produção deixa de usar diretamente `postgis/postgis`, pois a imagem upstream atualmente usada no desenvolvimento não fornece ARM64 para a versão escolhida. O projeto passa a construir PostGIS sobre a imagem oficial `postgres:17.11-trixie`, com pacotes PostGIS assinados.

Também foi introduzido um gate de soak de 24h. O M0 somente será considerado operacionalmente aprovado quando o relatório automático satisfizer os thresholds do ADR-018 no runtime real.

A API permanece bindada em localhost no primeiro deployment. Exposição pública será um marco separado, depois de edge/TLS/rate limiting.

## v0.7 — GTFS estático versionado

O feed GTFS oficial do Rio passa a ter download limitado, allowlist própria, validação rígida de ZIP/schema e manifest de proveniência identificado por SHA-256. Isso prepara rotas, paradas e horários para o futuro M1 (ETA + Confidence), mas não altera o gate realtime: o soak só começa com posições reais persistidas, em cache e com fingerprint observado.
