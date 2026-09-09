# ADR-016 — Latest observed position wins no estado hot

**Status:** Accepted — 2026-09-01

## Contexto
Pacotes GPS podem chegar atrasados ou fora de ordem. Um `SET` simples no cache permitiria que uma posição velha sobrescrevesse uma mais nova, fazendo o veículo retroceder no mapa.

## Decisão
A atualização de posição no Valkey é atômica via Lua e compara `observed_at` com o timestamp já armazenado. Posições estritamente mais antigas são ignoradas no estado hot, embora continuem elegíveis ao histórico PostgreSQL. Empates podem sobrescrever para permitir correções do mesmo instante.

A associação linha→veículo usa membro JSON em vez de delimitador textual, evitando ambiguidade caso identificadores externos contenham caracteres especiais.

## Consequências
O mapa mantém monotonicidade temporal por veículo, sem perder dados históricos tardios. A métrica `cached_records` passa a representar atualizações realmente aceitas pelo hot state.
