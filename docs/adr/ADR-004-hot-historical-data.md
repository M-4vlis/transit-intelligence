# ADR-004 — Separação de dados quentes e históricos
Status: Accepted

## Decisão
Último estado e caches ficam em Redis/Valkey; histórico durável em PostgreSQL/PostGIS com particionamento temporal.

## Razão
Evitar que consultas realtime concorram com análise histórica pesada.
