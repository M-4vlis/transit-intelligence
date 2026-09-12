# Transit Intelligence

Fundação técnica de um aplicativo comercial de mobilidade com foco em **previsão confiável, decisão de saída e inteligência operacional**, começando pelo transporte por ônibus do Rio de Janeiro.

> A marca comercial permanece desacoplada do código. Os identificadores técnicos usam `transit-intelligence` até a aprovação definitiva de uma marca sem colisões.

## Arquitetura inicial

```text
Mobile (React Native + Expo)
        |
        v
Edge / proteção
        |
        v
FastAPI — Modular Monolith
   |             |
 Valkey      PostgreSQL/PostGIS
   ^             |
   |             v
Realtime      Hot history
   ^             |
   |             v
Rio Adapter   Parquet ZSTD
   |             |
   v             v
Fonte SMTR   S3-compatible cold archive
             (OCI inicialmente / R2 compatível)
```

## Princípios já aplicados

- domínio independente da fonte externa;
- API oficial nunca é consultada diretamente pelo app;
- adapter tolerante + quarentena para schema drift;
- fingerprint do contrato observado por lote e canary agendado;
- HTTPS e allowlist para origens externas;
- idempotência, deduplicação e lease distribuído;
- PostGIS para consultas espaciais;
- Valkey para hot state, com **latest-position-wins** por `observed_at`;
- métricas Prometheus para API e worker;
- histórico frio em Parquet ZSTD fora da VPS em produção;
- archive com SHA-256, manifest e verificação remota integral;
- PostgreSQL não é data lake;
- retenção destrutiva desabilitada por padrão e fail-closed;
- API/worker realtime não carregam dependências pesadas de archive.

## Marco atual — v0.8.0 / M0 concluído

O M0 está operacionalmente concluído. O Transit Core manteve 24 horas de
ingestão real sem falhas, persiste no PostGIS, publica no Valkey e serve a API
própria. O histórico antigo foi arquivado no OCI Object Storage, restaurado e
validado integralmente antes de a retenção fail-closed liberar espaço no banco.

A chave destrutiva permanece desabilitada por padrão e foi ligada somente
durante a execução controlada e comprovada de retenção.

## Marco em desenvolvimento — M1 mapa + ETA básico

O backend do M1 está ativo na Oracle ARM64: borda HTTPS por túnel de saída,
catálogo GTFS versionado, mapa mobile e ETA V0 experimental com degradação
explícita. Perfis históricos por trecho e faixa horária são atualizados a cada
15 minutos e o avaliador de replay mede o erro contra chegadas posteriores.

O aplicativo de teste pesquisa e favorita linhas, usa localização sob demanda,
permite navegar no mapa, filtrar e identificar ônibus e consulta as próximas
paradas com ETA ao tocar num veículo. A validação final do refinamento M1.4 em
aparelho real e a adoção de um domínio definitivo permanecem pendentes.

Veja `docs/M0_TRANSIT_CORE.md` e `docs/VALIDATION.md`.


Runbooks operacionais: `docs/runbooks/FIRST_DEPLOYMENT_ORACLE_ARM64.md` e `docs/runbooks/SOAK_TEST_24H.md`.
