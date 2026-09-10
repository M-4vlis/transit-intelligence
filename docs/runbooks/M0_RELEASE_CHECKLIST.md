# M0 — Release checklist operacional

## Código / CI

- [x] testes unitários locais aprovados;
- [x] integração PostGIS/Valkey definida e aprovada no CI;
- [x] build multi-arquitetura do banco definido e aprovado no CI;
- [x] Compose de produção endurecido e testado estaticamente;
- [x] CI executado no repositório definitivo do produto;
- [x] lockfile de dependências gerado e revisado.

## Oracle ARM64

- [x] `.env.production` criado com permissões 600;
- [x] preflight aprovado;
- [x] imagem PostgreSQL/PostGIS construída em ARM64;
- [x] migrações aplicadas;
- [x] API `health/ready` saudável;
- [x] worker realtime saudável;
- [x] stack smoke aprovado com posição real.

## Fonte Rio

- [x] primeiro fingerprint live preservado;
- [x] rejection ratio inicial analisado;
- [x] canary do contrato executado externamente;
- [x] soak de 24h aprovado e JSON arquivado.

## Cold archive

- [x] bucket OCI criado fora da VPS;
- [x] object-store smoke aprovado;
- [x] archives Parquet remotos verificados;
- [x] restore checks integrais aprovados;
- [x] retenção destrutiva revisada, aplicada uma única vez e desativada novamente.

## Exposição pública — gate pós-M0 / M1

Estes itens não são necessários para encerrar o M0. Continuam bloqueando qualquer
acesso do aplicativo móvel à API pela internet.

- [ ] confirmar novamente que nenhum banco/cache será exposto no desenho de borda;
- [ ] definir edge/reverse proxy;
- [ ] instalar TLS válido;
- [ ] configurar WAF/rate limiting;
- [ ] revisar política de logs/PII;
- [ ] revisar threat model do endpoint público;
- [ ] liberar a API ao app móvel somente após todos os gates acima.
