# ADR-010 — Estratégia de fontes para o Rio

**Status:** Aceito

## Decisão
Separar três canais de dados:
1. realtime GPS para estado atual;
2. GTFS oficial para topologia e planejamento;
3. histórico oficial/próprio para analytics e ETA.

Nenhuma fonte externa será consumida diretamente pelo aplicativo mobile. Cada fornecedor/cidade terá adapter próprio e produzirá contratos canônicos internos.

## Motivo
Evita acoplamento ao schema municipal, permite cache central, controla carga externa, facilita failover e torna expansão geográfica incremental.
