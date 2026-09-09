# ADR-012 — Resiliência e idempotência da ingestão

**Status:** Accepted — 2026-09-01

## Decisão
A ingestão externa deve possuir:
- timeout explícito;
- retry somente para falhas transitórias, com exponential backoff + jitter;
- circuit breaker;
- validação de schema na borda;
- quarentena de registros inválidos;
- deduplicação em memória por lote e constraint idempotente no PostgreSQL;
- lease distribuído em Valkey para impedir dois coletores ativos da mesma fonte;
- nenhuma dependência do aplicativo mobile em relação à fonte municipal.

## Motivo
Fontes públicas podem atrasar, mudar schema, responder parcialmente ou ficar indisponíveis. A falha do upstream não pode corromper nosso estado nem produzir avalanche de requisições.
