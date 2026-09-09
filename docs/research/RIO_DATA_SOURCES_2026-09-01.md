# Fontes de dados do Rio — levantamento técnico inicial

Data de consolidação: 01/09/2026.

## 1. GPS dos ônibus / SPPO
A Secretaria Municipal de Transportes (SMTR) aponta o Data.Rio como fonte dos dados brutos de GPS usados no acompanhamento da operação. A documentação municipal de pipelines descreve registros de comunicação aproximadamente a cada 30 segundos e campos/tratamentos como posição, serviço, movimento, velocidade, parada e conformidade de trajeto.

### Uso no produto
- fonte primária de telemetria operacional;
- alimentar hot cache;
- alimentar Vehicle Quality Engine;
- alimentar ETA;
- gerar histórico próprio bruto/normalizado conforme política de retenção.

### Observação de robustez
A própria SMTR registra que existem falhas de comunicação GPS. Portanto, `frescura/freshness` e qualidade da telemetria devem ser parte explícita do domínio, nunca detalhe de UI.

## 2. Histórico GPS oficial
O catálogo técnico da Prefeitura documenta histórico de GPS do SPPO desde 01/03/2021, capturado a cada minuto, tratado ao longo do dia e disponibilizado no datalake. O histórico contém campos úteis como `flag_em_movimento`, `tipo_parada`, `status`, `velocidade_instantanea`, `velocidade_estimada_10_min` e distância entre registros.

### Uso no produto
- bootstrap de modelos estatísticos;
- benchmark do nosso algoritmo;
- análise de padrões por linha/trecho/faixa horária;
- criação de features de ETA V1/V2.

## 3. GTFS oficial
A SMTR publica GTFS e materiais auxiliares (itinerários KML, quadro horário) nos processos do Sistema RIO. A documentação operacional indica atualização periódica/mensal do GTFS.

### Uso no produto
- rotas, trips, shapes, stops e calendários;
- map matching;
- identificação de desvio de trajeto;
- cálculo de distância restante;
- construção do grafo de transporte.

## 4. Viagens identificadas por GPS / planejamento operacional
A Prefeitura documenta tabelas/algoritmos próprios para identificar viagens completas e medir conformidade com o planejado.

### Uso no produto
Não replicar cegamente o algoritmo municipal. Usá-lo como referência e benchmark para:
- detecção de início/fim de viagem;
- validação de shape;
- identificação de veículo fora de rota;
- qualidade da comunicação GPS.

## 5. Estratégia de ingestão

### Fonte realtime
Criar `RioRealtimeAdapter`, encapsulando o endpoint oficial vigente. O endpoint será configurável por ambiente e jamais hardcoded no app.

### Fonte estática
Criar `RioGtfsAdapter`, com snapshot versionado por `feed_version`/hash.

### Fonte histórica
Criar job separado de backfill, sem disputar recursos com realtime.

## 6. Contrato canônico interno
Todo dado externo deve ser convertido para `VehiclePosition` antes de entrar no restante do domínio. Campos específicos da fonte ficam em metadados/source DTOs e não vazam para o mobile.

## 7. Critérios de aceite da fonte realtime
Antes de iniciar coleta 24x7 em produção:
- endpoint oficial confirmado;
- termos/licença documentados;
- frequência real medida por pelo menos 24h;
- schema amostrado e versionado;
- timeout/retry/backoff implementados;
- circuit breaker lógico;
- métricas de latência, volume e erro;
- teste de mudanças inesperadas de schema;
- política de deduplicação definida.


## Atualização crítica — endpoint realtime confirmado
- Endpoint público oficial em uso: `https://dados.mobilidade.rio/gps/sppo`.
- Documento oficial da Prefeitura de 14/08/2025 cita explicitamente esse endpoint como API de posições em tempo real.
- Issue RJ-SMTR/pipelines_v3 #492, aberta em 07/08/2026, registra que a API mudou formato, campos e tipos e que sistemas internos precisaram ser compatibilizados.
- Decisão: nosso adapter suporta o contrato atual documentado e o formato legado columnar, com quarentena para registros incompatíveis.


## 8. Uso e proveniência
A triagem inicial do Portal da Transparência indica política municipal de dados abertos favorável a reutilização, inclusive para qualquer finalidade, sujeita à preservação da proveniência/abertura. Ainda assim, os termos específicos do endpoint GPS, GTFS e respectivos rate limits permanecem como gate jurídico-operacional antes do lançamento comercial. Ver `DATA_USAGE_AND_PROVENANCE_2026-09-01.md`.
