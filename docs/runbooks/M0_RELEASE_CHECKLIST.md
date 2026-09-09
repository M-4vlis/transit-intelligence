# M0 — Release checklist operacional

## Código / CI

- [x] testes unitários locais aprovados;
- [x] integração PostGIS/Valkey definida no CI;
- [x] build multi-arquitetura do banco definido no CI;
- [x] Compose de produção endurecido e testado estaticamente;
- [ ] CI executado no repositório definitivo do produto;
- [ ] lockfile de dependências gerado e revisado.

## Oracle ARM64

- [ ] `.env.production` criado com permissões 600;
- [ ] preflight aprovado;
- [ ] imagem PostgreSQL/PostGIS construída em ARM64;
- [ ] migrações aplicadas;
- [ ] API `health/ready` saudável;
- [ ] worker realtime saudável;
- [ ] stack smoke aprovado com posição real.

## Fonte Rio

- [ ] primeiro fingerprint live preservado;
- [ ] rejection ratio inicial analisado;
- [ ] canary do contrato executado externamente;
- [ ] soak de 24h aprovado e JSON arquivado.

## Cold archive

- [ ] bucket OCI/R2 criado fora da VPS;
- [ ] object-store smoke aprovado;
- [ ] primeiro archive Parquet remoto `verified`;
- [ ] restore check integral aprovado;
- [ ] retenção destrutiva revisada explicitamente.

## Exposição pública

- [ ] nenhum banco/cache exposto;
- [ ] edge/reverse proxy definido;
- [ ] TLS válido;
- [ ] WAF/rate limiting;
- [ ] política de logs/PII revisada;
- [ ] threat model do endpoint público revisado;
- [ ] somente após esses gates o app móvel poderá acessar a API pela internet.
