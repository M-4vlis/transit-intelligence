# ADR-031 — Candidato de confiança neutro ao método

## Status

Aceita em 2026-09-13.

## Contexto

A primeira observação com auditoria de diversidade mostrou linhas e células
espaciais bem distribuídas, mas 100% da faixa de alta confiança dependia de
`vehicle_recent_speed`. O candidato v2 concedia pontos diretamente pelo nome do
método, criando risco de confundir origem da evidência com qualidade observada.

## Decisão

O `m2-candidate-v3` não concede pontos pelo tipo do método. Os vinte pontos são
redistribuídos entre suporte amostral normalizado por método, dispersão da
velocidade e qualidade do casamento da viagem. Assim, qualquer método pode
atingir a faixa alta quando sua evidência é forte, recente, estável e bem casada.

Os limiares exploratórios passam a 85 para alta e 65 para média. O calibrador e
o resumo exigem explicitamente a versão v3, de modo que observações v2
preservadas não sejam misturadas. Dias posteriores ao ajuste constituirão a
evidência independente; o holdout e a revisão manual continuam obrigatórios.

## Consequências

- a fonte da velocidade permanece explicável, mas não determina a faixa por si;
- uma evidência fallback forte pode chegar a alta confiança;
- concentração acima de 95% em um método continua bloqueando a calibração;
- nenhuma resposta pública, ETA em produção ou tela mobile é alterada;
- `promotion_authorized=false` permanece invariável.
