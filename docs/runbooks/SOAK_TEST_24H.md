# Runbook — Soak test de 24 horas

## Objetivo

Demonstrar que o Transit Core consegue consumir a fonte oficial, normalizar, validar, persistir e publicar hot state continuamente antes de construirmos predição em cima dele.

## Evidências coletadas por ciclo

A tabela `transit.ingestion_runs` registra:

- status do ciclo;
- timestamps de início/fim;
- registros recebidos/rejeitados/deduplicados/persistidos/cacheados;
- contagem por qualidade;
- fingerprint e campos observados do contrato;
- tipo/detalhe resumido de falhas.

## Gate padrão

Para uma janela de 24h e polling de 60s, existem aproximadamente 1.440 ciclos esperados. O gate padrão calcula essa quantidade a partir de `RIO_POLL_INTERVAL_SECONDS` e exige pelo menos 90% de cobertura, além dos critérios do ADR-018.

Executar:

```bash
./infra/scripts/run_soak_gate.sh .env.production 24 | tee soak-24h.json
```

Em produção, `infra/scripts/soak_watch.sh` pode ficar armado durante uma
indisponibilidade da fonte. A janela começa somente no primeiro ciclo que
persiste e publica posições, com fingerprint de contrato presente. O watcher
grava estado em `ops/soak`, espera 24 horas completas e então executa o mesmo
gate sem reduzir qualquer threshold.

## Interpretação de falhas

- `cycle_coverage_low`: worker parado, reinícios excessivos, lease anormal ou ciclos muito lentos;
- `success_ratio_low`: indisponibilidade/falhas de rede/fonte;
- `rejection_ratio_high`: provável mudança ou degradação do schema externo;
- `contract_drift`: conjunto de campos observado mudou dentro da janela;
- `ingestion_gap_high`: interrupção relevante entre ciclos;
- `latest_run_stale`: worker não está processando neste momento;
- `no_positions_persisted`: pipeline não está gerando histórico;
- `no_positions_cached`: hot state não está sendo atualizado.

Não reduzir threshold automaticamente. Primeiro diagnosticar a causa e decidir se o critério inicial é irrealista ou se existe uma falha real.

## Pós-soak

Aprovação do soak autoriza avançar para o gate de archive, não para exclusão de dados. A sequência obrigatória é:

1. object-store smoke;
2. archive remoto real;
3. restore check integral;
4. só então revisão explícita de `DESTRUCTIVE_RETENTION_ENABLED`.
