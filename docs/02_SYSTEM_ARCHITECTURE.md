# 02 — System Architecture

## 1. Estilo arquitetural inicial
**Modular Monolith** com fronteiras de domínio explícitas.

Motivos:
- menor custo operacional;
- menor complexidade de deploy;
- transações simples;
- observabilidade centralizada;
- permite extração futura de módulos quando houver evidência de necessidade.

## 2. Componentes
```text
Mobile App (Expo/React Native)
        |
        v
Cloudflare / Edge
        |
        v
Reverse Proxy
        |
        v
FastAPI Modular Monolith
  |       |        |
  |       |        +-- Prediction
  |       +----------- Users/Preferences
  +------------------- Mobility Core
        |
  +-----+------------------+
  |                        |
  v                        v
Redis/Valkey          PostgreSQL + PostGIS
  ^                        |
  |                        v
Workers  <----  Transit Adapters      Parquet spool
  ^                                     |
  |                                     v
GTFS / APIs públicas              S3-compatible archive
                                  (OCI initially / R2 compatible)
```

## 3. Domínios iniciais
### Mobility
- agencies;
- routes;
- stops;
- trips;
- vehicle positions;
- service alerts;
- telemetry quality.

### Prediction
- ETA;
- segment travel time;
- confidence score;
- anomaly detection.

### User Preferences
- anonymous installation identity;
- favorites;
- notification preferences;
- optional account sync in later phase.

### Notification
- push subscriptions;
- alert rules;
- Smart Departure triggers.

## 4. Fluxo de ingestão
1. Adapter consulta fonte externa.
2. Payload é validado e normalizado.
3. Eventos inválidos são rejeitados/quarentenados.
4. Estado quente é atualizado no Redis.
5. Dados persistíveis são escritos no PostgreSQL/PostGIS.
6. Motor de qualidade classifica a telemetria.
7. Predição recalcula ETA/confidence quando necessário.
8. Clientes inscritos recebem apenas deltas relevantes.

## 5. Contrato canônico de posição
```text
VehiclePosition
- agency_id
- vehicle_id
- route_id
- trip_id?
- latitude
- longitude
- speed_mps?
- bearing_deg?
- observed_at
- received_at
- source
- quality_status
- quality_score
```

## 6. Dados quentes x históricos
### Redis/Valkey
- última posição por veículo, com atualização monotônica por `observed_at`;
- subscriptions;
- throttling/rate limit interno;
- cache de linha/parada;
- resultados transitórios de ETA.

### PostgreSQL/PostGIS
- topologia;
- GTFS;
- posições históricas particionadas por tempo;
- tempos de segmento agregados;
- eventos de qualidade;
- preferências persistidas quando aplicável.


### Cold archive
- Parquet com compressão ZSTD;
- partição lógica por fonte/ano/mês/dia;
- SHA-256 e contagem de linhas registrados em manifest;
- object storage S3-compatible fora da VPS em produção;
- revalidação remota antes de retenção destrutiva.

## 7. Estratégia realtime
WebSocket/SSE para atualização de mapa e estado de linha.
- cliente assina tópicos por linha/região;
- servidor envia deltas;
- heartbeat;
- backpressure;
- limite de subscriptions por conexão;
- fallback para polling moderado.

## 8. Escala inicial
### Estágio A
1 VPS:
- reverse proxy;
- API;
- worker;
- PostgreSQL/PostGIS;
- Redis/Valkey.

### Estágio B
Separar banco/cache e escalar API horizontalmente.

### Estágio C
Extrair ingestão/realtime/prediction somente quando métricas demonstrarem gargalo.

## 9. Regras de dependência
- módulos de domínio não dependem de FastAPI;
- adapters externos implementam interfaces do núcleo;
- camada API traduz HTTP para casos de uso;
- infraestrutura depende do domínio, nunca o contrário;
- modelos de banco não vazam como contratos públicos da API.

## 10. Resiliência
- timeouts obrigatórios em chamadas externas;
- retries com jitter e limites;
- circuit breaker em fontes instáveis;
- idempotência na ingestão;
- deduplicação por chave temporal/veículo;
- fila local/recuperação quando fonte ou banco falhar;
- degradação graciosa: exibir último dado com indicação clara de idade.

## 11. Observabilidade
- logs estruturados JSON;
- correlation/request id;
- métricas RED/USE;
- tracing OpenTelemetry;
- health/readiness endpoints;
- alertas de ingestão parada;
- métricas específicas de ETA e qualidade de GPS.
