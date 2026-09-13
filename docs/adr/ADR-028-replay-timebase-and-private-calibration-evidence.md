# ADR-028 — Base temporal do replay e evidência privada de calibração

## Status

Aceita em 2026-09-13.

## Contexto

O primeiro replay procurava a chegada a partir do horário da posição GPS e
comparava os limites de ETA, relativos ao instante de avaliação, com a duração
desde aquela posição. Essa mistura podia incluir uma passagem já ocorrida e
subestimar a cobertura dos intervalos. Médias agregadas também não preservavam
evidência suficiente para recalibrar score e intervalos posteriormente.

## Decisão

1. A chegada observada deve ocorrer depois do instante em que a previsão é
   avaliada.
2. ETA previsto, ETA real e limites usam todos esse mesmo instante como origem.
3. Relatórios corrigidos recebem `evaluation_schema_version=2`; versões
   anteriores não contam para gates de calibração.
4. Cada chegada elegível registra uma observação de calibração com score, erros,
   limites, método, rota e fatores do score.
5. Não são registrados identificadores de veículo, viagem, shape ou parada.
6. O calibrador separa datas inteiras para holdout e nunca muda produção nem
   autoriza promoção automática.

## Consequências

As coortes antigas permanecem imutáveis para auditoria exploratória, mas a
janela formal de calibração recomeça com o schema 2. O conjunto fica suficiente
para calcular intervalos empíricos e validar separação das bandas sem reter
identidade operacional individual.
