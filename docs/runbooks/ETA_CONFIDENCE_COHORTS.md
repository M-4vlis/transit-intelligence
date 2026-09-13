# Coleta contínua de coortes de confiança do ETA

## Objetivo

Acumular evidência independente para calibrar o Confidence Score do M2 sem
intervenção manual e sem alterar a retenção do histórico. A rotina é somente de
leitura no PostgreSQL.

## Agenda e custo operacional

O timer executa a cada três horas, em oito faixas do dia. Cada execução usa no
máximo 35% de uma CPU e 768 MiB, com prioridade baixa de CPU e I/O. Relatórios
JSON ocupam pouco espaço e são preservados por prazo indeterminado durante a
calibração.

Unidades:

- `transit-intelligence-eta-confidence-cohort.timer`;
- `transit-intelligence-eta-confidence-cohort.service`.

## Artefatos

Diretório padrão:

`/home/ubuntu/artifacts/transit-intelligence/confidence-cohorts`

Cada execução cria um `cohort-<UTC>.json`, um `summary-<UTC>.json`, atualiza o
link `summary-latest.json` e acrescenta os SHA-256 ao arquivo `SHA256SUMS`.
Coortes são deduplicadas pelo instante efetivo da âncora ao gerar o resumo.

Também cria `calibration-<UTC>.json` e atualiza `calibration-latest.json`. Esse
relatório permanece `insufficient_data` até satisfazer dias, faixas horárias,
volume por banda, diversidade de rotas e holdout. Mesmo depois disso, o máximo
que pode retornar é `candidate_for_manual_review`; promoção automática é
proibida.

Ao fim de cada execução, os três JSON imutáveis e uma fotografia do
`SHA256SUMS` são enviados ao Object Storage configurado. Cada upload é relido
integralmente e comparado por tamanho, SHA-256 e metadado remoto. O manifesto
mais recente referencia todo o conjunto acumulado, permitindo reconstrução
completa. O estado local evita reenvios e rejeita alteração de um artefato já
arquivado.

## Operação

```bash
sudo systemctl status transit-intelligence-eta-confidence-cohort.timer
systemctl list-timers transit-intelligence-eta-confidence-cohort.timer
sudo journalctl -u transit-intelligence-eta-confidence-cohort.service -n 50
cat /home/ubuntu/artifacts/transit-intelligence/confidence-cohorts/summary-latest.json
cat /home/ubuntu/artifacts/transit-intelligence/confidence-cohorts/calibration-latest.json
sudo /usr/local/sbin/transit-intelligence-archive-confidence-evidence
sudo /usr/local/sbin/transit-intelligence-restore-confidence-evidence
```

O restore check também roda diariamente. Ele baixa o manifesto mais recente e
todos os objetos referenciados em diretório temporário, verifica SHA-256 remoto,
tamanho e cada entrada do `SHA256SUMS`, e apaga a cópia temporária ao terminar.
Ele nunca restaura sobre o diretório de produção.

## Monitor operacional

O timer `transit-intelligence-eta-confidence-monitor.timer` roda a cada 30
minutos e grava `operations-latest.json`. Ele falha e deixa evidência no journal
se ocorrer qualquer um destes casos:

- coorte automática com mais de cinco horas;
- falha anterior do coletor ou do restore check;
- checksum inválido ou conflitante;
- evidência local ausente do estado confirmado no Object Storage;
- link latest inválido;
- drift material: aumento de MAE acima de 60 segundos e 50%, ou queda de
  cobertura do intervalo acima de 15 pontos percentuais.

O drift só começa a ser comparado quando há seis coortes no schema temporal
atual; antes disso, o estado explícito é `insufficient_history`, sem falso
alarme.

```bash
cat /home/ubuntu/artifacts/transit-intelligence/confidence-cohorts/operations-latest.json
sudo systemctl status transit-intelligence-eta-confidence-monitor.timer
sudo journalctl -u transit-intelligence-eta-confidence-monitor.service -n 50
```

Execução manual segura:

```bash
sudo systemctl start transit-intelligence-eta-confidence-cohort.service
```

O `flock` encerra com sucesso uma segunda execução se já houver outra ativa.

## Critério de acompanhamento

Revisar o resumo após 7 dias e novamente após 14 e 30 dias. A coleta pode
continuar além desses marcos. O candidato só poderá ser publicado quando as
faixas forem monotônicas em dados independentes e os intervalos estiverem
calibrados. O volume de amostras, isoladamente, não autoriza promoção.

O bloco `calibration_coverage` do resumo acompanha automaticamente dias locais,
faixas do dia e o mínimo de 50 resultados por banda usando apenas a amostragem
determinística atual. Coortes exploratórias antigas continuam no histórico, mas
não contam para esses gates.

## Interrupção reversível

```bash
sudo systemctl disable --now transit-intelligence-eta-confidence-cohort.timer
```

Isso interrompe novas coletas e não remove relatórios nem altera dados do banco.
