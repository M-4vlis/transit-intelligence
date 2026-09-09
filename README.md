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

## Marco atual — v0.7.1

O M0 inclui um deployment endurecido na Oracle ARM64, Object Storage validado e um gate automatizado de soak. A v0.7 acrescentou a aquisição segura e versionada do GTFS oficial do Rio como preparação paralela para o futuro motor de ETA/Confidence.

A v0.7.1 adaptou o coletor realtime ao contrato atual da fonte oficial, que exige `dataInicial` e `dataFinal`. A stack está implantada na Oracle ARM64, a ingestão real está persistindo no PostGIS e publicando no Valkey, e o soak de 24 horas começou em `2026-09-03T14:11:27Z`. Object Storage e restore foram revalidados; a retenção destrutiva continua desabilitada.

Veja `docs/M0_TRANSIT_CORE.md` e `docs/VALIDATION.md`.


Runbooks operacionais: `docs/runbooks/FIRST_DEPLOYMENT_ORACLE_ARM64.md` e `docs/runbooks/SOAK_TEST_24H.md`.
