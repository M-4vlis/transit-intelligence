# ADR-032 — Candidato de confiança sensível ao horizonte

## Contexto

Após sete datas independentes, o candidato v3 separou o erro agregado, mas a
faixa alta concentrou 95,33% das observações no método de velocidade recente do
próprio veículo. Ele também não representava o aumento natural da incerteza em
previsões mais distantes.

Elevar apenas o corte da faixa alta melhorou o erro, mas falhou no holdout por
concentrar 97,9% da faixa alta no mesmo método. Relaxar o gate de diversidade
para aprovar esse resultado foi rejeitado.

## Decisão

Criar `m2-candidate-v4` mantendo o score independente do nome do método e
introduzindo uma penalidade auditável pelo ETA previsto:

- até 180 segundos: 0 ponto;
- de 181 a 360 segundos: -10 pontos;
- de 361 a 600 segundos: -20 pontos;
- acima de 600 segundos: -30 pontos.

Os cortes provisórios são 79 para alta e 65 para média. A regra foi escolhida
somente com as datas de treinamento de 13 a 17/09. A verificação retrospectiva
de 19 e 20/09 foi registrada apenas como sanity check e não conta como novo
holdout cego. A validação formal do v4 será prospectiva.

O v4 usa observação de calibração schema 3 e contrato privado `m2-shadow-v2`.
Relatórios v2 e v3 continuam imutáveis e são excluídos da calibração v4.

## Consequências

- previsões longas deixam de receber confiança alta apenas por GPS recente;
- métodos de ETA continuam neutros no cálculo;
- a coleta de 14 dias do v4 reinicia o relógio da promoção;
- os três dias mais recentes são holdout;
- nenhuma faixa v4 é publicada automaticamente.
