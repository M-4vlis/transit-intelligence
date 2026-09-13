# Oracle ARM64 — M2: trabalho paralelo à calibração

Data: 2026-09-13 14:34 UTC

Commit implantado: `16586e6`

## Resultado

Os seis itens planejados para avançar enquanto as coortes acumulam foram
implantados na VPS ARM64 (`aarch64`) e validados em produção.

1. Evidências M2 arquivadas de forma incremental no OCI Object Storage. O
   restore mais recente baixou e verificou 35 objetos contra metadados, manifesto
   e `SHA256SUMS`.
2. Contrato privado `m2-shadow-v1` gerado por observação, sempre
   `publishable=false`, ausente da API pública.
3. Monitor operacional a cada 30 minutos cobrindo atraso/falha de coortes,
   checksums, completude remota e drift. Estado final: `passed`, sem falhas nem
   avisos.
4. Classificação shadow fora de operação. Na coorte real de 14:19 UTC: 23
   prováveis parados fora de serviço, 6 prováveis reposicionamentos, 9
   inconclusivos e 4 não aplicáveis. Todos mantiveram ETA proibido.
5. Relatório de prontidão imutável, com checksum e cópia remota. Estado:
   `collecting`; promoção automática: falsa.
6. Medição diária de orçamento. Estado: `warning` preventivo, sem falha de
   limite gratuito projetado.

## Evidência operacional

- testes locais: 157 aprovados e 9 integrações ignoradas sem dependências reais;
- GitHub Actions do commit final: `success`;
- coorte de produção: `sufficient_data`, schema temporal 2 e contrato shadow;
- API local: banco e cache prontos;
- API pública: busca da linha 870 respondeu corretamente;
- fonte Rio direta: HTTP 200, 7.520 registros;
- fingerprint direto e persistido:
  `b8a3775b7ce4415241a1ba377303da6801f6c089d5c26dac8c370871465c1e33`;
- ingestão mais recente: 13.076 recebidos, 10.972 persistidos, 12.308 enviados ao
  cache e zero rejeitados;
- Valkey: 2.210 chaves de posição, amostra com TTL positivo;
- seis containers principais em execução, cinco saudáveis, zero reinícios;
- `.env.production` preservado com SHA-256
  `800e640768673f08f3190719d868fbb8e5df3412508e91307776c4ddd384570a`;
- `DESTRUCTIVE_RETENTION_ENABLED=false`.

## Orçamento medido

- forma: 2 CPUs lógicas e 12.506.804.224 bytes de memória;
- memória disponível: 10.944.991.232 bytes;
- containers: 451.983.441 bytes e 29,42% de CPU instantânea somados;
- filesystem raiz: 43 GiB usados de 96 GiB (45%);
- volumes Docker: 31,11 GB;
- Object Storage atual: 1.616.057.747 bytes;
- cinco Parquets completos: 1.615.698.034 bytes, média de 323.139.606 bytes/dia;
- projeção conservadora em 30 dias: 11.633.461.607 bytes;
- requisições mensais projetadas pelo M2: 21.180.

A projeção excede o teto preventivo interno de 10 GB, mas permanece abaixo dos
20 GB e das 50 mil requisições mensais documentados para Object Storage Always
Free. O crescimento local também exige uma política de retenção verificada antes
de um soak prolongado. Nenhuma exclusão foi habilitada neste deploy.

## Timers ativos

- `transit-intelligence-eta-confidence-cohort.timer`;
- `transit-intelligence-confidence-evidence-restore.timer`;
- `transit-intelligence-eta-confidence-monitor.timer`;
- `transit-intelligence-m2-resource-budget.timer`.
