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

## Operação

```bash
sudo systemctl status transit-intelligence-eta-confidence-cohort.timer
systemctl list-timers transit-intelligence-eta-confidence-cohort.timer
sudo journalctl -u transit-intelligence-eta-confidence-cohort.service -n 50
cat /home/ubuntu/artifacts/transit-intelligence/confidence-cohorts/summary-latest.json
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
