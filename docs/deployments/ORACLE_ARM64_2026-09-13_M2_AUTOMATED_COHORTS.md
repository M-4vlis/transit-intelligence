# Oracle ARM64 — coortes automáticas do M2 — 2026-09-13

## Resultado

A coleta read-only do Confidence Score foi instalada como timer persistente na
VPS ARM64. Ela executa oito vezes ao dia, sobrevive a reinicializações e não
exige intervenção do usuário.

## Controles preservados

- `.env.production` permaneceu com SHA-256
  `800e640768673f08f3190719d868fbb8e5df3412508e91307776c4ddd384570a`;
- `DESTRUCTIVE_RETENTION_ENABLED=false`;
- nenhum container do stack foi reiniciado;
- PostgreSQL, Valkey, API, ingestion, edge proxy e tunnel permaneceram ativos;
- todos os containers apresentaram `RestartCount=0` após a instalação;
- replay limitado a 35% de uma CPU e 768 MiB, com baixa prioridade de CPU/I/O.

## Primeira execução

- unidade: `transit-intelligence-eta-confidence-cohort.service`;
- resultado: `success`, exit code `0`;
- duração observada: 7 segundos;
- relatórios anteriores importados: 7;
- coortes após a execução: 8;
- chegadas observadas acumuladas: 550;
- espaço ocupado: 48 KiB;
- checksums: todos aprovados com `sha256sum -c`.

No agregado inicial, 4 de 8 coortes foram monotônicas. O candidato permanece
`uncalibrated` e não está exposto ao passageiro.

## Fonte ao vivo durante a mudança

O ingestion worker continuou recebendo HTTP 200 da fonte oficial do Rio. Um lote
posterior à instalação recebeu 2.805 registros, rejeitou zero, persistiu 1.786 e
atualizou 2.410 entradas de cache. O fingerprint observado foi
`b8a3775b7ce4415241a1ba377303da6801f6c089d5c26dac8c370871465c1e33`.

## Acompanhamento

Revisões programadas após 7, 14 e 30 dias. A coleta permanece ativa além desses
marcos até a conclusão da calibração, salvo interrupção operacional explícita.
