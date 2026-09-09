# ADR-014 — Durable cold archive through an S3-compatible boundary

**Status:** Accepted — 2026-09-01

## Contexto
O histórico de GPS é um ativo do produto, mas o disco local da VPS não é um domínio de falha independente do PostgreSQL. Um arquivo Parquet no mesmo host não pode ser considerado backup suficiente para permitir exclusão destrutiva das partições hot.

## Decisão
- o writer Parquet local existe apenas para desenvolvimento, testes e spool temporário;
- produção usa uma interface **S3-compatible** genérica;
- OCI Object Storage é o alvo inicial preferencial por já existir infraestrutura Oracle e franquia Always Free;
- Cloudflare R2 permanece alternativa/segunda origem compatível sem alteração do Transit Core;
- cada objeto é validado localmente antes do upload e remotamente por leitura integral + SHA-256 após o upload;
- o manifest só passa a `verified` após a verificação remota;
- imediatamente antes de qualquer `DROP PARTITION`, o objeto remoto é revalidado novamente;
- a retenção também compara `row_count` com o hot store e se recusa a apagar partições compartilhadas por mais de uma fonte;
- indisponibilidade do storage, divergência de hash ou objeto ausente bloqueiam a retenção.

## Consequências
A retenção fica mais conservadora e exige uma leitura remota adicional por arquivo, mas reduz drasticamente o risco de perda silenciosa do nosso histórico. A operação diária gera poucas chamadas de object storage, adequadas ao estágio inicial.
