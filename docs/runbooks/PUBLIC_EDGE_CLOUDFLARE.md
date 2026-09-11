# Public edge — Cloudflare Tunnel

## Pré-requisitos

- domínio sob uma conta Cloudflare controlada pelo projeto;
- hostname dedicado, por exemplo `api.dominio.tld`;
- tunnel remoto configurado com o serviço de origem exato
  `http://edge-proxy:8080`;
- token do connector tratado como segredo.

Nenhuma regra de entrada HTTP/HTTPS adicional deve ser criada na Oracle para o
Transit. O conector é somente de saída. A porta 443 do host pertence à API HTTPS
do Atualiza_materiais e o SSH deve permanecer somente na porta 22.

## Preparar o segredo na VPS

```bash
cd /home/ubuntu/apps/transit-intelligence
install -d -m 700 .secrets
printf '%s' 'TOKEN_COPIADO_DO_CLOUDFLARE' > .secrets/cloudflare-tunnel-token
chmod 600 .secrets/cloudflare-tunnel-token
```

O token não deve ser enviado em chat, log, Git ou argumento de processo.

Adicionar ao `.env.production`:

```dotenv
PUBLIC_API_HOSTNAME=api.dominio.tld
CLOUDFLARE_TUNNEL_TOKEN_FILE=/home/ubuntu/apps/transit-intelligence/.secrets/cloudflare-tunnel-token
CORS_ALLOWED_ORIGINS=
```

Aplicativo nativo não depende de CORS. Se houver cliente web, preencher apenas
com a origem HTTPS exata, nunca com `*`.

## Validar e iniciar

```bash
./infra/scripts/edge_preflight.sh .env.production
./infra/scripts/deploy_edge.sh .env.production
```

O deploy executa um smoke pela mesma rede usada pelo túnel e prova que:

- `/v1/` chega à API;
- `/metrics` e `/health/ready` retornam 404;
- métodos mutáveis são bloqueados;
- cabeçalhos de segurança estão presentes.

## Gate externo

Depois do tunnel ficar `HEALTHY`, validar de uma rede externa:

```bash
curl --fail --show-error --silent --dump-header - \
  "https://api.dominio.tld/v1/routes/483/vehicles" -o /dev/null
curl --show-error --silent --output /dev/null --write-out '%{http_code}\n' \
  "https://api.dominio.tld/metrics"
```

O primeiro comando deve retornar 200 com TLS válido. O segundo deve retornar
404. Também confirmar no Cloudflare que TLS está em modo estrito, que o hostname
não revela um registro direto para o IP da VPS e que as regras de WAF/bot
mitigation disponíveis estão ativas.

## Rollback

```bash
docker compose --env-file .env.production \
  -f infra/docker-compose.production.yml --profile edge \
  stop cloudflared edge-proxy
```

Isso remove a entrada pública sem interromper ingestão, API local, banco ou
cache. Revogar o token no painel Cloudflare encerra connectors remanescentes.
