# ADR-018 — Gate operacional de soak antes de ETA

**Status:** Aceito
**Data:** 2026-09-01

## Contexto

O valor futuro do produto depende da qualidade e continuidade da série histórica. Um backend que passa testes unitários, mas perde ciclos de GPS, sofre drift silencioso ou deixa de persistir posições, não é uma base aceitável para o motor de ETA.

## Decisão

Antes de iniciar o ETA Engine, executar no runtime real um soak de no mínimo 24 horas e avaliá-lo automaticamente.

Critérios iniciais padrão:

- cobertura de pelo menos 90% dos ciclos esperados;
- taxa de sucesso de pelo menos 98%;
- rejeição de registros de no máximo 2%;
- nenhum gap entre ciclos superior a 180 segundos;
- último ciclo com no máximo 120 segundos de idade no momento da avaliação;
- recebimento, persistência e cache de posições reais maiores que zero;
- no máximo um fingerprint de contrato durante a janela.

Os thresholds são deliberadamente configuráveis. Alterações devem ser justificadas e registradas, nunca feitas somente para transformar um soak falho em aprovado.

## Consequências

- evolução do ETA fica condicionada a evidência operacional;
- falhas da fonte externa permanecem visíveis e mensuráveis;
- o relatório de soak se torna artefato de release do Transit Core.
