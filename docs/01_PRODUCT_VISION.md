# 01 — Product Vision

## 1. Visão
Construir um assistente inteligente de mobilidade urbana que não se limite a exibir a posição de veículos, mas ajude o usuário a decidir **quando sair, qual veículo esperar, quando desistir de uma opção e qual alternativa tomar**.

## 2. Problema central
Soluções existentes exibem GPS, itinerários e ETAs, porém o passageiro ainda sofre com:
- posições defasadas ou inconsistentes;
- veículos “fantasma”;
- ETAs voláteis;
- pouca transparência sobre a confiabilidade da previsão;
- baixa personalização da decisão de viagem;
- ausência de histórico útil para entender regularidade real.

## 3. Proposta de valor
> “Saiba quando seu ônibus realmente vai chegar — e qual é a melhor decisão para você tomar agora.”

## 4. Diferenciais planejados
1. **Confidence Score** por previsão/veículo.
2. **Vehicle Quality Engine** para detectar telemetria suspeita.
3. **Smart Departure** baseado em rotina e chegada desejada.
4. Histórico operacional próprio por linha, trecho e faixa horária.
5. Crowdsourcing opcional e privacy-first.
6. Arquitetura multi-cidade baseada em adapters e GTFS/GTFS-RT.
7. Camada futura de analytics B2B/B2G.

## 5. MVP
O MVP deve provar três hipóteses:
- usuários valorizam previsão mais confiável do que mero mapa em tempo real;
- um score de confiança melhora a tomada de decisão;
- histórico operacional melhora ETA em relação ao cálculo puramente geométrico.

### Escopo funcional MVP
- mapa com veículos de linhas selecionadas;
- busca de linhas e paradas;
- favoritos locais;
- ETA V0/V1;
- score de confiança;
- indicador de idade do GPS;
- push de aproximação;
- histórico básico de regularidade;
- funcionamento sem cadastro obrigatório.

### Fora do MVP
- roteamento multimodal completo;
- pagamentos;
- marketplace;
- chat social;
- gamificação complexa;
- microsserviços;
- Kubernetes.

## 6. Métricas iniciais
### Produto
- DAU/MAU;
- retenção D1, D7 e D30;
- sessões por usuário/dia;
- linhas favoritas por usuário;
- notificações abertas.

### Qualidade
- MAE do ETA;
- erro P50/P90;
- percentual de previsões com confiança alta que ficam dentro da tolerância;
- taxa de GPS stale;
- taxa de veículos detectados como inconsistentes.

### Negócio
- conversão free → premium;
- ARPU;
- CAC quando houver mídia paga;
- churn premium;
- custo de infraestrutura por 1.000 MAU.

## 7. Monetização
### B2C
- Free com publicidade discreta e recursos essenciais.
- Premium: Smart Departure, alertas avançados, histórico, rotinas, comparações e experiência sem anúncios.

### B2B/B2G
- dashboards de confiabilidade;
- regularidade/headway;
- qualidade de telemetria;
- APIs e datasets agregados;
- estudos operacionais.

## 8. Princípios de privacidade
- minimizar coleta;
- não exigir conta para funções básicas;
- não armazenar histórico individual de localização por padrão;
- crowdsourcing somente por opt-in explícito;
- retenção curta de dados brutos colaborativos;
- agregação antes de uso analítico;
- direito de exclusão e exportação quando houver conta.

## 9. Estratégia geográfica
Começar no Rio de Janeiro e desenhar desde o primeiro dia uma camada de normalização que permita incluir novas cidades sem alterar o núcleo do produto.

## 10. Roadmap macro
1. Fundação e ingestão.
2. Mapa + ETA básico.
3. Confidence Score.
4. Smart Departure.
5. Crowdsourcing.
6. Multimodal.
7. Analytics.
8. Expansão geográfica.
9. API comercial.
