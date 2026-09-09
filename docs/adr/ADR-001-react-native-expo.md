# ADR-001 — React Native + Expo
Status: Accepted

## Decisão
Usar React Native com TypeScript e Expo como base do aplicativo.

## Razões
- uma base para Android/iOS;
- bom fluxo de desenvolvimento em Windows/Linux;
- build remoto para iOS;
- ecossistema amplo;
- facilidade de OTA update para partes compatíveis.

## Consequências
Manter abstrações para mapas, notificações e storage para reduzir lock-in.
