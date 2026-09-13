# M2 — Confidence Score

## Objetivo

Transformar a incerteza técnica do ETA em uma indicação calibrada, explicável e
útil. O aplicativo só poderá chamar uma previsão de baixa, média ou alta
confiança depois que cada faixa demonstrar esse comportamento em chegadas reais.

## Fatias de entrega

### M2.0 — Candidato interno

- [x] definir fatores e pesos iniciais auditáveis;
- [x] manter o candidato fora da resposta pública e da interface;
- [x] produzir score, faixa provisória, componentes e motivos estáveis;
- [x] segmentar o replay por faixa candidata;
- [x] executar a primeira bateria multicoorte na Oracle, com 528 chegadas
  observadas e separação preliminar das três faixas.

### M2.1 — Calibração

- [x] ampliar o conjunto rotulado inicial para pelo menos 300 chegadas
  observadas;
- [ ] cobrir pico, entrepico, noite e dias independentes;
- [ ] garantir pelo menos 50 resultados por faixa que será publicada;
- [ ] demonstrar MAE e P90 monotônicos entre alta, média e baixa confiança;
- [ ] recalibrar intervalos e medir cobertura por faixa;
- [ ] verificar que uma linha, região ou método não domina artificialmente uma
  faixa.

### M2.2 — Contrato público

- [ ] congelar versão do algoritmo e limites calibrados;
- [ ] publicar nível, faixa de chegada e motivos explicáveis na API;
- [ ] manter indisponibilidade honesta quando não houver evidência;
- [ ] adicionar métricas e alertas de drift da calibração.

### M2.3 — Experiência mobile

- [ ] apresentar confiança sem sugerir precisão inexistente;
- [ ] explicar em linguagem simples por que a confiança caiu;
- [ ] validar cores, texto, acessibilidade e compreensão em aparelho real;
- [ ] integrar os componentes ao redesign obrigatório antes da beta.

## Fatores do candidato inicial

O score interno de 0 a 100 combina recência da posição, distância da projeção ao
shape, origem da evidência de velocidade, quantidade de amostras, dispersão da
velocidade e qualidade do casamento com a viagem. Pesos e limites são
deliberadamente simples e auditáveis; ainda não representam probabilidade.

## Regra de segurança

Até a conclusão da calibração, o campo existente continua sendo
`experimental`. Números e faixas candidatas aparecem apenas no replay interno e
não podem ser mostrados ao passageiro.

## Definição de pronto

O M2 termina quando o score separa erros futuros de forma repetível em dados não
usados no ajuste, a API explica o resultado sem excesso de confiança e o teste
mobile confirma que usuários entendem ETA, intervalo e nível de confiança.
