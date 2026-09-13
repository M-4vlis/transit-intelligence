# ADR-029 — Evidência de confiança durável e restaurável

## Status

Aceita em 2026-09-13.

## Contexto

A calibração do M2 depende de coortes acumuladas por semanas. Manter a única
cópia no disco da VPS tornaria a evidência vulnerável a perda do volume ou da
instância. Uma simples confirmação de upload também não prova que o objeto pode
ser lido e restaurado corretamente.

## Decisão

Arquivar cada coorte, resumo e calibração imutáveis no Object Storage
S3-compatible já configurado. Todo objeto novo é relido integralmente e
verificado por tamanho e SHA-256. Um manifesto remoto versionado referencia o
conjunto acumulado e uma fotografia do `SHA256SUMS` local.

Um teste independente diário restaura o manifesto mais recente e todos os seus
objetos em armazenamento temporário. Além do hash declarado nos metadados e no
manifesto, ele valida cada JSON contra o `SHA256SUMS` restaurado. O teste nunca
escreve no diretório ativo.

## Consequências

- perda da VPS não elimina a evidência de calibração;
- colisão ou alteração de artefato imutável falha de forma fechada;
- o estado incremental reduz requisições e custo;
- a retenção destrutiva continua desabilitada;
- excluir objetos continua sendo uma ação manual fora desta automação.
