# ADR-027 — Amostragem determinística do replay de ETA

## Status

Aceita em 2026-09-13.

## Contexto

O replay selecionava a posição mais recente de cada veículo e aplicava o limite
de amostras após ordenar por agência e identificador. Assim, coortes sucessivas
avaliavam principalmente os mesmos primeiros 200 veículos, criando viés por
frota, linha e região.

Durante a investigação, o feed GTFS oficial foi baixado novamente. Seu SHA-256
`a99f925460e7628b6eeecb9952430542c06b3e2800afa8ba7f9765fd2e6f26f1`
coincidiu exatamente com o snapshot ativo, descartando desatualização do catálogo
como causa imediata.

## Decisão

Depois de escolher uma única posição por veículo, o replay ordena os candidatos
pelo MD5 de agência, veículo e instante da âncora. Uma âncora fixa produz a mesma
amostra; âncoras diferentes distribuem a seleção pela frota. O relatório registra
`sampling_method=deterministic_vehicle_hash_v1`.

## Consequências

Coortes antigas continuam válidas como evidência exploratória, mas comparações
de calibração para promoção pública devem priorizar coortes produzidas pelo novo
método. A mudança não afeta ingestão, API ou cálculos apresentados no app.
