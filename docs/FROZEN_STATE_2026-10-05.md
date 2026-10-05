# Estado congelado — 5 de outubro de 2026

## Decisão operacional

O projeto foi congelado por decisão do proprietário enquanto aguarda nova
hospedagem. A ingestão terminou em `2026-10-05T23:07:39Z`. Todos os timers do
Transit, o coletor, a API, a borda, PostgreSQL e Valkey devem permanecer
desligados. Os serviços das outras aplicações da VPS não fazem parte deste
congelamento.

O código versionado não contém `.env.production`, credenciais do OCI, token do
Cloudflare nem chaves privadas. Esses segredos devem ser recuperados da conta
correspondente ou recriados na retomada.

Estado final da VPS após a preservação remota:

- nenhum container, volume, rede ou imagem Docker do Transit permanece;
- todos os timers e o serviço de soak do Transit estão desabilitados;
- nenhum serviço do Transit está ativo;
- filesystem raiz em 13%, com aproximadamente 85 GB disponíveis;
- aproximadamente 10 GiB de RAM disponíveis;
- containers das aplicações `atualiza-materiais` e `deploy` permaneceram
  ativos e saudáveis;
- permanecem apenas a cópia de release protegida, incluindo o `.env.production`
  local, e o repositório Git bare: cerca de 5,1 MB no total;
- os artifacts locais foram removidos depois da verificação remota e podem ser
  recuperados pelo prefixo de congelamento no Object Storage.

## Posição do produto

- **M0 Transit Core:** concluído e comprovado em produção ARM64.
- **M1 mapa e ETA básico:** concluído; APK validado em aparelho Android real.
- **M2 Confidence Score:** candidato `m2-candidate-v4` pronto para revisão
  manual, mas nunca promovido ao contrato público.
- **Visual:** funcional, ainda provisório; a modernização visual permanece um
  gate obrigatório antes de beta pública.

## Resultado da coleta

Período observado: `2026-09-02` a `2026-10-05`.

| Medida | Resultado |
|---|---:|
| Ciclos de ingestão | 43.713 |
| Ciclos bem-sucedidos | 39.740 |
| Registros recebidos | 326.129.467 |
| Posições persistidas | 215.084.526 |
| Registros rejeitados pelo adapter | 0 |
| Fingerprints de contrato observados | 1 |
| Falhas `TransitSourceUnavailable` | 2.997 |
| Circuit breaker aberto | 588 |
| Timeouts | 387 |
| Outros erros de resposta | 1 |

A taxa global de ciclos bem-sucedidos foi 90,9%, afetada principalmente pelo
bootstrap inicial e por indisponibilidades da fonte. Depois da estabilização,
os dias completos ficaram normalmente próximos de 99%. Houve lacunas relevantes
em 18 de setembro e 1º de outubro.

O contrato da fonte permaneceu estável e nenhum registro foi para quarentena.

## Dados preservados

### Histórico frio

O Object Storage contém 33 manifests verificados entre `2026-09-01` e
`2026-10-04`, cobrindo 206.737.962 posições e 11.472.919.766 bytes de Parquet.
Os dias sem coleta geraram archives vazios verificáveis. O dia parcial de 5 de
outubro não foi preservado como posição bruta; seus perfis e resultados
derivados estão no backup essencial.

O orçamento medido antes do congelamento era 11.545.177.499 bytes. Com o backup
essencial adicional, o total permanece abaixo de 12 GB e não crescerá enquanto
o projeto estiver congelado.

### Snapshot essencial

Prefixo remoto:

`transit-history/_freeze/20261005/`

Objetos principais:

| Objeto | Bytes | SHA-256 |
|---|---:|---|
| `transit-essential.dump` | 176.926.511 | `e05f2212320b9a34aed5f688342670d93294dba2b36876cb675af2b031119dd3` |
| `final-evidence.tar.gz` | 5.103 | `e8170999bd2859b6efe4ab6be0eca929f95f3505f653e3b2c724b9b4afa8f22b` |
| `remote-manifest.json` | 1.210 | `7f255033707ff9d1ee0e7b50e594572cb8fe46f2b2cece33d6698b0efa744962` |

O mesmo prefixo contém `SHA256SUMS`, contagens de origem/restauração e a
política que confirma `raw_vehicle_positions_restored=0`.

O dump foi restaurado integralmente em um PostgreSQL temporário isolado. As
contagens de origem e restauração coincidiram:

| Conjunto essencial | Linhas |
|---|---:|
| Rotas GTFS | 494 |
| Pontos GTFS | 7.694 |
| Viagens GTFS | 17.361 |
| Horários de parada | 1.031.419 |
| Pontos de shapes | 361.022 |
| Perfis históricos de ETA | 12.295.198 |
| Execuções de ingestão | 43.713 |
| Manifests de archive | 33 |

Valkey e as posições quentes foram excluídos da preservação por serem
reconstruíveis. O dump mantém schemas, migrations, catálogo, perfis, manifests
e metadados operacionais.

## Resultado do M2

A calibração final reuniu 6.623 resultados em 15 dias independentes, com 14
dias elegíveis e todas as faixas/períodos cobertos. Todos os gates automáticos
de calibração passaram.

| Faixa | Holdout | MAE | P90 do erro | Cobertura do intervalo | Erro > 300 s |
|---|---:|---:|---:|---:|---:|
| Alta | 559 | 80,6 s | 141,0 s | 80,0% | 7,2% |
| Média | 762 | 113,6 s | 516,9 s | 77,6% | 12,7% |
| Baixa | 163 | 285,0 s | 831,8 s | 77,9% | 33,7% |

Conclusão: a ordenação das faixas é coerente e o candidato está tecnicamente
pronto para revisão manual. A faixa baixa continua muito imprecisa e não deve
ser apresentada ao passageiro como promessa de horário. A promoção ficou
bloqueada apenas pelo gate operacional/orçamentário e continua exigindo decisão
manual explícita.

## Retomada em nova hospedagem

1. Clonar o branch `main` do GitHub e verificar este documento.
2. Provisionar Docker em ARM64 ou AMD64. Para retomar coleta contínua, usar pelo
   menos 2 OCPUs, 12 GB de RAM e 80–100 GB de disco, mantendo o histórico bruto
   no Object Storage.
3. Criar `.env.production` a partir de `.env.example`; gerar novos segredos e
   configurar credenciais S3-compatible com acesso ao archive existente.
4. Baixar `remote-manifest.json`, `SHA256SUMS`, `transit-essential.dump` e
   `final-evidence.tar.gz` do prefixo de congelamento e validar SHA-256.
5. Subir somente `postgres` e `redis`.
6. Copiar o dump para PostgreSQL e executar, num banco vazio:

   ```bash
   pg_restore -U transit_app -d transit \
     --no-owner --no-acl --exit-on-error transit-essential.dump
   ```

7. Rodar migrations, smoke do Object Storage e uma restauração amostral dos
   Parquets antes de ativar retenção ou ingestão.
8. Recalcular o orçamento, revisar a política de histórico frio e só então
   habilitar os timers e o coletor.
9. Reavaliar manualmente o candidato M2 com dados novos; não publicar o score
   antigo automaticamente.
10. Discutir e aprovar o redesign visual antes de produzir a beta pública.

## Critério de preservação

O histórico frio foi mantido porque é o ativo caro e não reproduzível do
projeto, permanece dentro da cota gratuita congelada e permite recalibrar ETAs.
Na VPS, somente código, configuração secreta protegida e documentação mínima
permanecem. Containers, imagens, cache, artifacts e volumes de dados do Transit
foram removidos depois da verificação remota acima.
