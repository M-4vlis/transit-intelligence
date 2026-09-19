# Oracle ARM64 — auditoria de retenção e continuidade M2

Data: 2026-09-19 UTC

Commit implantado: `9d47388`

CI: <https://github.com/M-4vlis/transit-intelligence/actions/runs/35454882974>

## Incidente encontrado

A coleta parou em 17/09 às 17:58 UTC. Os logs persistentes mostram um comando
externo de desligamento às 17:50, seguido por várias reinicializações via
`SIGINT`. O último boot não chegou a permanecer ativo. Não houve OOM, falta de
disco, corrupção do PostgreSQL nem falha causada pelo ciclo de retenção.

A instância foi recuperada em 19/09. PostgreSQL, Valkey, API, edge e ingestão
subiram automaticamente; o PostgreSQL iniciou como primário e recuperou o
volume persistente sem erro.

## Retenção verificada

O timer persistente recuperou automaticamente a janela perdida e concluiu o
fluxo completo entre 16:09 e 16:22 UTC:

- arquivo de 17/09: 6.162.585 linhas, 345.595.186 bytes e SHA-256 verificado;
- arquivo vazio de 18/09: 0 linhas, 1.608 bytes e restauração independente
  aprovada;
- preflight: dias candidatos 10/09 e 11/09, nenhum dia protegido;
- apply: somente 10/09 e 11/09 removidos;
- partições quentes finais: 12/09 a 17/09 e 19/09;
- configuração preservada: `HOT_RETENTION_DAYS=7` e
  `DESTRUCTIVE_RETENTION_ENABLED=true`;
- próximo ciclo: 20/09, aproximadamente 03:17 UTC.

O Object Storage contém 371 objetos e 5.978.873.583 bytes. Os 17 Parquet
históricos somam 5.970.077.399 bytes. Nenhum objeto frio foi removido.

## Saúde depois da recuperação

- API pronta, com banco e cache verdadeiros;
- stack smoke aprovado com posição recente;
- Valkey respondeu `PONG` e continha 5.362 chaves;
- 18 ciclos de ingestão após o boot: 147.057 registros recebidos, 101.147
  persistidos, 133.685 atualizações de cache e zero rejeitados;
- fonte oficial ao vivo: 11.043 recebidos/válidos, zero rejeitados e fingerprint
  `b8a3775b7ce4415241a1ba377303da6801f6c089d5c26dac8c370871465c1e33`;
- filesystem raiz em 46%, com 53 GiB livres e cerca de 10 GiB de memória
  disponível;
- suíte local: 164 testes aprovados, 9 integrações ignoradas sem dependências
  reais e Ruff aprovado;
- os cinco jobs da CI passaram, inclusive build PostgreSQL ARM64, integração,
  Compose e mobile.

## Continuidade M2

O monitor operacional agora mede intervalos entre coortes nas últimas 72 horas
e bloqueia gaps acima de cinco horas. Em produção ele detectou corretamente o
intervalo de 48,526 horas entre 17/09 15:35 UTC e 19/09 16:06 UTC. O estado
`failed` atual do monitor é intencional e impede que uma coorte nova esconda a
indisponibilidade; ele deixa de bloquear quando a lacuna sair da janela móvel.

O resumo já cobre seis datas locais e todas as faixas superam 50 resultados.
A calibração v3 usa cinco dias independentes completos, 2.044 resultados e
passa os gates de horário, linha, região e método. O marco de sete dias não
deve ser declarado em 20/09 apenas pelo calendário: a indisponibilidade de
18/09 deslocou a revisão confiável em aproximadamente um a dois dias.

## Orçamento

A projeção permanece abaixo do teto OCI Always Free de 20 GB, mas acima do
limite conservador interno de 10 GB. O histórico frio continua imutável; uma
política destrutiva de expiração no bucket não foi ativada.
