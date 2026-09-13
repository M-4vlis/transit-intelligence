# Orçamento de recursos do M2

## Limites usados

A política é deliberadamente mais conservadora que a franquia documentada pela
Oracle. O serviço falha antes de alcançar:

- 2 OCPUs e 12 GiB de memória na forma Ampere A1;
- 80% do filesystem raiz;
- 10 GiB somando projeto e artefatos locais;
- 10 GB projetados no Object Storage;
- 30 mil requisições mensais projetadas pelo M2.

A Oracle documenta 1.500 OCPU-horas, 9.000 GB-horas, equivalentes a 2 OCPUs e
12 GB para contas Always Free, além de 20 GB combinados de Object Storage e 50
mil requisições mensais. Fonte oficial:
https://docs.oracle.com/pt-br/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm

O teto interno de 10 GB e 30 mil requisições deixa margem para o histórico e
outros usos da tenancy. A medição não enxerga recursos de outras instâncias ou
buckets; por isso o relatório marca explicitamente
`tenancy_wide_usage_not_observed=true`.

Ultrapassar apenas a projeção interna de 10 GB gera `status=warning`, mantendo o
timer saudável enquanto ainda houver margem até os 20 GB documentados. Exceder
o limite gratuito projetado, ou qualquer limite imediato de host, gera
`status=failed` e falha o serviço.

## Automação

O timer `transit-intelligence-m2-resource-budget.timer` roda diariamente. Ele
mede CPU e memória instantâneas dos containers Transit, memória e disco do host,
tamanho local do projeto e objetos/bytes reais no prefixo remoto. A projeção de
30 dias considera oito coortes por dia, dois manifestos por coorte e restore
integral diário.

```bash
sudo systemctl start transit-intelligence-m2-resource-budget.service
cat /home/ubuntu/artifacts/transit-intelligence/confidence-cohorts/budget-latest.json
sudo systemctl status transit-intelligence-m2-resource-budget.timer
```

Cada relatório é imutável, recebe SHA-256 e é arquivado no mesmo Object Storage
das evidências. Nenhuma rotina deste fluxo exclui dados ou habilita retenção.
