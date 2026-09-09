# ADR-013 — Retenção hot somente após archive verificado

**Status:** Aceito — 2026-09-01

## Contexto
O GPS gera volume alto e contínuo. PostgreSQL/PostGIS é excelente para consultas operacionais recentes, mas não deve ser usado como data lake de histórico bruto indefinido na infraestrutura inicial.

## Decisão
- histórico bruto frio será armazenado em **Parquet** em object storage/armazenamento compatível;
- cada arquivo frio terá manifesto com dia, origem, contagem de linhas, tamanho e SHA-256;
- uma partição hot só poderá ser removida quando existir manifesto com status `verified` para aquele dia/origem;
- a contagem de linhas do archive deve coincidir com a contagem hot da origem no instante da retenção;
- se a partição diária contiver qualquer outra origem, ela permanece protegida;
- writers e retenção usam o mesmo advisory lock por partição; o `DROP` só ocorre após uma rechecagem atômica da contagem dentro da transação;
- ausência, falha ou inconsistência do archive implica **não apagar** a partição;
- retenção é executada por serviço próprio, separado da ingestão realtime.

## Consequências
- falha fechada contra perda silenciosa de dados;
- PostgreSQL permanece pequeno e previsível;
- o histórico continua apropriado para analytics/ML;
- writer Parquet e verificação de checksum foram implementados na v0.5; ativação destrutiva em produção continua bloqueada até validação integrada com object storage externo e teste de restauração.
