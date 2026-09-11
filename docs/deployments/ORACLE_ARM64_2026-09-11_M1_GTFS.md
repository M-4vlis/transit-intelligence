# Oracle ARM64 — M1.1 GTFS catalog — 2026-09-11

## Resultado

- a URL antiga do item ArcGIS passou a responder 403 e foi substituída pelo
  endpoint canônico atual `https://dados.mobilidade.rio/gtfs/schedule`;
- o canário validou o ZIP oficial de 25.321.196 bytes, 107.473.944 bytes
  expandidos e SHA-256
  `a99f925460e7628b6eeecb9952430542c06b3e2800afa8ba7f9765fd2e6f26f1`;
- a primeira carga foi executada com `--no-activate`, mantendo a API sem dados
  parciais;
- a segunda execução reconheceu o mesmo SHA-256, não duplicou linhas e ativou o
  snapshot já importado;
- busca por linha e paradas próximas respondeu usando somente o snapshot ativo.

## Contagens do snapshot ativo

| Arquivo | Linhas |
|---|---:|
| agency.txt | 5 |
| routes.txt | 494 |
| stops.txt | 7.694 |
| trips.txt | 17.361 |
| stop_times.txt | 1.031.419 |
| calendar.txt | 3 |
| calendar_dates.txt | 30 |
| shapes.txt | 361.022 |

## Evidência operacional

- `/v1/routes?query=483` retornou cinco variantes oficiais;
- `/v1/stops/nearby` retornou paradas ordenadas por distância na região da
  Central do Brasil;
- o stack smoke passou com banco, cache e posição recente; idade observada de
  29,476 segundos;
- a API permaneceu sem saída para a Internet;
- o Object Storage smoke e o restore integral de 4.744.463 linhas do arquivo de
  2026-09-07 passaram antes desta implantação.

## Porta 443 compartilhada

O listener SSH exclusivo que interrompia o HTTPS do Atualiza_materiais foi
substituído por `sslh`. O listener público em 443 separa TLS para o Caddy em
`127.0.0.1:8443` e SSH para o daemon com chave em `127.0.0.1:22022`. O firewall
persistente permite apenas 80/443; 22 permanece negada. SSH, HTTPS e os dois
stacks foram validados novamente após reboot.

## Segurança

- `DESTRUCTIVE_RETENTION_ENABLED=false` permaneceu inalterado;
- nenhum snapshot GTFS ou histórico Parquet foi removido;
- snapshots GTFS anteriores permanecem disponíveis para rollback explícito;
- o endpoint público do Transit continua bloqueado até existir domínio ativo na
  conta Cloudflare e o gate HTTPS externo passar.
