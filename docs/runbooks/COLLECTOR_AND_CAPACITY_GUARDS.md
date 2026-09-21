# Guardas de continuidade e capacidade

## Watchdog local do coletor

O timer `transit-intelligence-collector-watchdog.timer` verifica a cada três
minutos a prontidão da API e a métrica do último ciclo bem-sucedido. Ele falha
fechado quando a coleta fica há mais de cinco minutos sem sucesso e preserva o
último relatório em:

`/home/ubuntu/artifacts/transit-intelligence/operations/collector-watchdog-latest.json`

Esse watchdog detecta worker travado, banco/cache indisponível e atraso da
coleta enquanto o host está ligado. Ele não consegue avisar quando a própria
VPS está desligada; para isso é obrigatório um alarme externo da OCI ou outro
monitor fora da instância.

## Alarme externo da OCI

O monitor externo foi ativado em 20/09/2026 sem depender da VPS:

- tópico: `transit-intelligence-ops-email`;
- alarme: `Transit VPS telemetry absent`;
- namespace: `oci_computeagent`;
- sinal: ausência de `CpuUtilization` agrupada pelo identificador da instância;
- persistência exigida: dez minutos;
- severidade: `CRITICAL`;
- repetição enquanto ativo: a cada 24 horas;
- assinatura: e-mail confirmado e ativo, sem endereço armazenado no repositório.

O alarme cobre host desligado, agente sem telemetria e perda ampla de
conectividade. O watchdog local continua sendo a verificação mais rápida para
falhas do coletor com a VPS ligada.

## Object Storage

O orçamento diário mede o prefixo real e usa quatro níveis:

- 10 GB: aviso conservador;
- 15 GB: aviso elevado;
- 18 GB: falha operacional preventiva;
- 20 GB: limite gratuito documentado, nunca tratado como margem utilizável.

O relatório estima quantos dias faltam para cada nível usando o tamanho médio
dos Parquets completos. Nenhuma rotina exclui objetos automaticamente.

Antes de uma política de 30 dias ser ativada:

1. auditar o consumo total da tenancy, inclusive outros buckets;
2. definir uma segunda cópia verificável ou aceitar explicitamente a expiração;
3. testar a restauração dessa cópia;
4. preservar manifestos e evidências agregadas;
5. exigir decisão manual antes da primeira remoção de histórico frio.
