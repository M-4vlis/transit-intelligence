# ADR-031 — Classificação shadow de veículos fora de operação

## Status

Aceita em 2026-09-13.

## Decisão

Veículos que não podem ser associados com segurança a uma viagem continuam sem
ETA. Para diagnóstico interno, um veículo a pelo menos 500 metros do trajeto é
classificado de forma conservadora:

- até 0,5 m/s: `probable_out_of_service_stationary`;
- acima de 0,5 m/s: `probable_deadhead_or_repositioning`;
- velocidade ausente: `probable_out_of_service_speed_unknown`.

Distância menor ou evidência de outro tipo permanece `off_route_unclassified`
ou `not_applicable`. Todos esses estados mantêm `eta_permitted=false`.

## Consequências

A avaliação passa a separar provável garagem/terminal de reposicionamento sem
inventar horários e sem esconder problemas de casamento GTFS. A classificação
permanece shadow até ser validada em diferentes dias e horários; ela não altera
a API nem o aplicativo nesta etapa.
