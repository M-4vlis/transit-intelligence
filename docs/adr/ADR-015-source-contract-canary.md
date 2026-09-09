# ADR-015 — Canary independente para o contrato da fonte do Rio

**Status:** Accepted — 2026-09-01

## Contexto
A API oficial do Rio já alterou campos e tipos em produção. Fazer o CI de cada commit depender da disponibilidade dessa API criaria builds flakey; não verificar a fonte até um usuário reclamar seria pior.

## Decisão
- testes normais usam fixtures versionadas e determinísticas;
- um workflow separado consulta a fonte pública a cada 6 horas e também pode ser disparado manualmente;
- o canary falha se não houver posições válidas ou se >=5% dos registros forem rejeitados pelo contrato;
- ele registra fingerprint e campos observados como artefato de CI;
- após a primeira captura live aprovada, os fingerprints aceitos poderão ser fixados via `EXPECTED_RIO_CONTRACT_FINGERPRINTS`.

## Consequências
O pipeline de desenvolvimento permanece determinístico e a integração externa recebe monitoramento próprio, com detecção de schema drift sem acoplamento aos deploys.
