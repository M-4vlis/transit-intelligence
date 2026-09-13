# ADR-030 — Contrato shadow do Confidence Score

## Status

Aceita em 2026-09-13.

## Decisão

O primeiro contrato de confiança é `m2-shadow-v1` e existe somente nos
artefatos privados de replay. Ele registra versão do algoritmo candidato,
score, nível candidato, janela de chegada e motivos estáveis.

O contrato é fechado por construção: `exposure=internal_only`,
`publishable=false` e o estado é `withheld_uncalibrated` ou
`withheld_pending_manual_review`. Nem mesmo um resultado candidato do
calibrador autoriza publicação automática.

A API pública e o aplicativo não recebem nenhum desses campos. Uma futura
mudança de exposição exigirá outro contrato, evidência em holdout e decisão
manual registrada.
