# ADR-011 — Hot operational data vs. cold historical archive

**Status:** Accepted — 2026-09-01

## Contexto
A telemetria de uma cidade inteira gera milhões de posições. Manter todo o bruto indefinidamente no PostgreSQL da VPS elevaria custo, I/O, backup e risco operacional.

## Decisão
- Valkey mantém estado ao vivo com TTL curto.
- PostgreSQL/PostGIS mantém posições brutas recentes em partições diárias, inicialmente com retenção-alvo de 48 horas.
- Dados antigos serão compactados em Parquet particionado por data/fonte e enviados a object storage antes da remoção do hot store.
- Agregados de viagem/segmento úteis ao ETA permanecem no PostgreSQL por prazo longo.
- A aplicação pública nunca consulta Parquet bruto diretamente no caminho crítico.

## Consequências
Preservamos o histórico proprietário sem transformar o banco transacional em data lake. O mecanismo de compactação/arquivamento será implementado antes de habilitar retenção automática destrutiva.

## Nota de capacidade inicial
Com milhares de veículos reportando a cada ~30 segundos, sete dias de posições com índices podem consumir dezenas de GB. A janela de 48h reduz o risco de exaurir o disco da VPS. Nenhuma exclusão automática será habilitada antes do arquivamento Parquet estar validado e com restore testado.
