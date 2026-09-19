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
- [x] automatizar oito coortes diárias, com relatórios imutáveis, SHA-256 e
  resumo reproduzível;
- [x] cobrir pico, entrepico e noite;
- [ ] cobrir sete dias independentes na janela de calibração;
- [x] garantir pelo menos 50 resultados por faixa que será publicada;
- [ ] demonstrar MAE e P90 monotônicos entre alta, média e baixa confiança;
- [ ] recalibrar intervalos e medir cobertura por faixa;
- [x] verificar que uma linha, região ou método não domina artificialmente uma
  faixa.

A observação de calibração schema 2 acrescenta somente uma célula espacial
grossa de aproximadamente 2,5 km, sem coordenada exata. O calibrador mede, em
cada faixa, quantidade e maior participação de linhas, células e métodos. Uma
faixa fica bloqueada se tiver menos de dez linhas, menos de três células, mais
de 20% em uma linha, mais de 50% em uma célula ou mais de 95% em um método.
Relatórios schema 1 continuam preservados, mas não são misturados nesta nova
calibração.

O candidato `m2-candidate-v3` remove a pontuação direta pelo nome do método de
ETA. Suporte amostral, dispersão e qualidade do casamento passam a usar os vinte
pontos redistribuídos. Os limiares provisórios de 85/65 foram escolhidos com a
amostra exploratória do primeiro dia; somente dias posteriores podem validá-los.
O calibrador filtra explicitamente a versão candidata, impedindo mistura com o
`m2-candidate-v2` preservado.

O replay também registra cauda de erros acima de cinco minutos, viés, cobertura
e métricas separadas por método de ETA, forma de casamento e linhas mais
representadas. Distâncias de projeção dos veículos excluídos ajudam a distinguir
GPS fora do trajeto de problemas no casamento com o GTFS. A distribuição de
velocidade dos excluídos ajuda a identificar veículos parados em garagens ou
terminais sem relaxar o limite geométrico de segurança.

As coortes usam uma amostra reproduzível por hash de veículo e instante da
âncora. Isso distribui a avaliação pela frota e evita repetir os primeiros
identificadores em ordem lexicográfica.

Somente relatórios com a base temporal corrigida (`evaluation_schema_version=2`)
podem alimentar a calibração. Cada resultado elegível preserva score, erro,
intervalo, método e fatores técnicos, mas omite veículo, viagem, shape e parada.
O calibrador offline separa os dois dias mais recentes como holdout e nunca
autoriza promoção automática.

O contrato `m2-shadow-v1` já materializa, somente nas observações privadas, o
nível candidato, a janela de chegada e os motivos explicáveis. Ele traz
`publishable=false` por construção e não faz parte do schema da API pública.

Cada coorte gera ainda um `readiness-<UTC>.json`, com checksum e cópia no Object
Storage. O relatório combina cobertura, holdout, monotonicidade, cobertura dos
intervalos, saúde operacional e completude do backup. Seu melhor estado possível
é `candidate_for_manual_review`; `promotion_authorized` permanece sempre falso.

O monitor operacional também audita continuidade recente. Um intervalo maior
que cinco horas entre coortes dentro das últimas 72 horas bloqueia a prontidão,
mesmo que o serviço já tenha reiniciado e produzido uma coorte nova. Isso evita
que a recuperação do host esconda uma lacuna real na observação.

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

## Janela de observação

A coleta automática permanece ativa enquanto o M2 estiver em calibração. Os
marcos de revisão são 7, 14 e 30 dias, sem prazo máximo rígido. Desenvolvimento
da API, diagnósticos do ETA e modernização visual podem avançar em paralelo;
somente a promoção pública do score depende da evidência acumulada.

## Definição de pronto

O M2 termina quando o score separa erros futuros de forma repetível em dados não
usados no ajuste, a API explica o resultado sem excesso de confiança e o teste
mobile confirma que usuários entendem ETA, intervalo e nível de confiança.
