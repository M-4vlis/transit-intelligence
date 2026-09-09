# ADR-002 — Modular Monolith
Status: Accepted

## Decisão
Iniciar com monólito modular em vez de microsserviços.

## Razões
Menor custo e complexidade sem sacrificar fronteiras de domínio.

## Regra de extração
Um módulo só vira serviço independente mediante evidência: gargalo, escala independente, necessidade de isolamento ou ownership separado.
