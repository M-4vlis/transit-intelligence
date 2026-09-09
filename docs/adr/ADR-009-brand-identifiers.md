# ADR-009 — Separar marca comercial de identificadores técnicos

**Status:** Aceito

## Contexto
A preferência comercial “NoPonto” apresentou colisões no mesmo segmento durante validação preliminar.

## Decisão
Usar identificadores técnicos neutros (`transit-intelligence`) até a marca definitiva passar por validação. Package names, bundle IDs, domínios e namespaces permanentes não dependerão da marca provisória.

## Consequência
Uma futura mudança de nome não exige renomear banco, serviços, imagens Docker, pacotes ou infraestrutura crítica.
