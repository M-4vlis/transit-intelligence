# Validation Log

## Foundation v0.5 — 01/09/2026

### Escopo validado localmente

A v0.5 amplia o M0 com:

- contratos de domínio e fingerprint determinístico de posições;
- adapter Rio compatível com a família atual/documentada e formato legado;
- coerção defensiva de identificadores numéricos/string e timestamps epoch s/ms;
- tratamento explícito do envelope de erro `RetornoOK=false`;
- Vehicle Quality Engine V0;
- HTTP resiliente com timeout, retry, backoff, jitter, circuit breaker, limite de payload, HTTPS e allowlist;
- cliente realtime isolado de proxies herdados do ambiente (`trust_env=False`);
- quarentena, deduplicação e telemetria de ingestão;
- canary de contrato da fonte separado do CI normal, agendado a cada 6 horas;
- PostGIS e partições diárias para histórico quente;
- Valkey com lease distribuído e atualização monotônica por `observed_at`;
- writer Parquet ZSTD em streaming;
- writer S3-compatible genérico para OCI Object Storage, R2 ou outro backend compatível;
- SHA-256 local e leitura remota integral para verificação do cold archive;
- manifest canônico por fonte/dia;
- retenção destrutiva desabilitada por padrão;
- retenção fail-closed com revalidação remota imediatamente antes do `DROP PARTITION`;
- imagens da API/ingestão sem `pyarrow`/`boto3`; dependências de archive ficam em extra separado;
- CI preparado para PostGIS 17 + Valkey 8 e pipeline Postgres → Parquet → manifest.

### Testes executados neste ambiente

```bash
cd backend
pytest -q
python -m compileall -q app tests scripts
cd ..
git diff --check
```

Também foi validado o parse de `infra/docker-compose.yml` com PyYAML.

Resultado local:

```text
48 passed
4 skipped
compileall: OK
git diff --check: OK
compose YAML parse: OK
```

Os quatro `skipped` são deliberados: exigem PostGIS/Valkey reais ou `pyarrow`, indisponíveis neste runtime.

### Gates não simulados

Este ambiente não possui Docker, PostGIS/Valkey executáveis nem `pyarrow` e não consegue abrir diretamente a origem realtime. Por isso **não** estamos tratando como validados ainda:

- integração real PostgreSQL/PostGIS;
- integração real Valkey/Lua;
- pipeline integrado Postgres → Parquet real → manifest;
- primeira captura live do endpoint do Rio;
- fingerprint live congelado;
- upload/verificação contra OCI Object Storage ou R2 reais;
- restore de archive remoto;
- soak test do coletor;
- Ruff e `pip-audit` locais.

O CI contém gates para Ruff, `pip-audit`, PostGIS, Valkey, migrations, archive Parquet e validação do Compose. O canary da fonte fica em workflow independente para não tornar cada deploy dependente da disponibilidade da Prefeitura.

### Reprodutibilidade de dependências

O `pyproject.toml` usa faixas compatíveis e separa dependências de runtime das de archive. A tentativa de gerar lockfile offline neste runtime não pôde ser concluída porque nem todos os pacotes estavam no cache. **Nenhuma release de produção será feita sem lockfile/requisitos congelados gerados em ambiente com resolver disponível.**

### Evidência externa relevante

O endpoint configurado é `https://dados.mobilidade.rio/gps/sppo`. A própria SMTR documenta esse endpoint em código aberto e, em 07/08/2026, registrou incidente no monitoramento após mudança de campos e tipos da fonte realtime. Isso justifica a separação por adapter, quarentena, fingerprints e canary.

### Próximo gate operacional

1. publicar a base em um repositório remoto e deixar CI/canary executarem;
2. capturar a primeira resposta live sanitizada e aprovar o fingerprint observado;
3. executar a stack PostGIS + Valkey e as migrations em ambiente real;
4. configurar um bucket externo S3-compatible, inicialmente OCI Object Storage;
5. executar upload, verificação e teste de restauração do primeiro Parquet;
6. rodar soak test de ingestão por pelo menos 24 horas;
7. somente depois iniciar retenção automática/coleta histórica contínua de produção.

## v0.6 — validação local e gates pendentes

Validação executada localmente após inclusão do deployment ARM64 e soak gate:

- `pytest -q`: 65 passed, 5 skipped (integrações dependentes de PostGIS/Valkey/PyArrow);
- `python -m compileall`: aprovado;
- parse YAML de Compose e workflows: aprovado;
- `bash -n` nos scripts de operação: aprovado;
- `git diff --check`: aprovado.

### Descoberta de compatibilidade

A imagem `postgis/postgis:17-3.5` não é adequada para a VPS Oracle AArch64 porque seu upstream declara apenas `amd64`. A v0.6 substitui essa dependência em produção por uma imagem própria baseada em `postgres:17.11-trixie`, que possui variante ARM64, instalando o pacote PostGIS disponível para ARM64.

### Ainda não comprovado neste runtime

- build Docker `linux/arm64` da imagem customizada;
- conexão live com `https://dados.mobilidade.rio/gps/sppo`;
- PostGIS + Valkey reais no runtime Oracle;
- stack smoke com posição real;
- soak de 24 horas;
- object storage externo e restore.

Esses itens permanecem gates explícitos; não são tratados como aprovados por inferência.
