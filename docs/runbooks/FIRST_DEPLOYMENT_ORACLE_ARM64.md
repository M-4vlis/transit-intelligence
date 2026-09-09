# Runbook — Primeiro deployment na Oracle ARM64

Este runbook coloca o Transit Core em operação **sem exposição pública**. API e métricas ficam bindadas somente em `127.0.0.1`; PostgreSQL e Valkey não publicam portas no host.

## 1. Pré-requisitos do host

- Linux ARM64/AArch64;
- Docker Engine + plugin Docker Compose;
- usuário operacional com acesso ao Docker;
- no mínimo 4 GiB RAM e 8 GiB livres antes do primeiro build;
- relógio do sistema sincronizado (NTP);
- repositório clonado a partir da fonte oficial do projeto.

Não abrir 5432, 6379, 8000 ou 9101 no firewall público.

## 2. Criar configuração local de produção

Na raiz do projeto:

```bash
cp infra/production.env.example .env.production
chmod 600 .env.production
```

Gerar senhas aleatórias fortes, por exemplo:

```bash
openssl rand -hex 32
```

Preencher `POSTGRES_PASSWORD` e `CACHE_PASSWORD`. No primeiro soak, manter:

```text
DESTRUCTIVE_RETENTION_ENABLED=false
ARCHIVE_STORAGE_KIND=local
```

A retenção destrutiva só poderá ser habilitada depois do teste de object storage + restore.

## 3. Preflight

```bash
./infra/scripts/preflight.sh .env.production
```

O comando não inicia serviços. Ele valida Docker/Compose, arquitetura, memória, disco, permissões do arquivo de segredos, comprimento mínimo das credenciais e configuração do Compose.

## 4. Deploy

```bash
./infra/scripts/deploy.sh .env.production
```

O deploy:

1. constrói a imagem PostgreSQL/PostGIS e as imagens da aplicação;
2. inicia PostgreSQL e Valkey;
3. executa migrações;
4. inicia API e ingestão realtime;
5. aguarda healthchecks.

## 5. Verificação imediata

```bash
./infra/scripts/status.sh .env.production
```

Após o primeiro lote realtime:

```bash
docker compose \
  --env-file .env.production \
  -f infra/docker-compose.production.yml \
  --profile operations \
  run --rm stack-smoke
```

O smoke só aprova se PostgreSQL, Valkey e uma posição recente do Rio estiverem disponíveis.

## 6. Iniciar soak

Não é necessário iniciar um processo especial: o worker já registra evidências de cada ciclo em `transit.ingestion_runs`. Registrar a hora de início e deixar o stack operar sem intervenção por pelo menos 24 horas.

Evitar reinícios, alterações de configuração e deploys durante a janela, salvo para corrigir incidente real. Se houver mudança, reiniciar a contagem da janela.

## 7. Avaliar 24 horas

```bash
./infra/scripts/run_soak_gate.sh .env.production 24
```

Exit code `0` = aprovado. Exit code `2` = gate reprovado. O JSON impresso deve ser preservado como evidência do marco.

## 8. Antes de exposição pública

O fato de o stack estar saudável não autoriza exposição direta da porta 8000. O próximo gate de segurança adicionará edge/reverse proxy, TLS, rate limiting e proteção DDoS antes do app móvel acessar a API pela internet.

## 9. Object storage e restore (depois do soak)

Depois de configurar um bucket externo S3-compatible no `.env.production`, ainda com `DESTRUCTIVE_RETENTION_ENABLED=false`:

```bash
./infra/scripts/object_store_smoke.sh .env.production
```

Esse smoke envia um objeto aleatório de 4 KiB, faz download, compara SHA-256/metadados e remove o objeto de teste.

Depois de gerar um archive real de um dia, validar a restauração integral:

```bash
./infra/scripts/archive_restore_check.sh .env.production YYYY-MM-DD
```

O restore check baixa o objeto registrado como `verified`, recalcula SHA-256, abre o Parquet e compara número de linhas e tamanho. Somente após um restore aprovado será avaliada a ativação da retenção destrutiva.
