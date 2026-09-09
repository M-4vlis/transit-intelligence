# 03 — Security Architecture

## 1. Objetivo
Segurança deve ser requisito arquitetural, não etapa de publicação.

## 2. Referências
- OWASP MASVS para mobile.
- OWASP API Security Top 10.
- princípio do menor privilégio.
- privacy by design e privacy by default.

## 3. Modelo de ameaça inicial
Ativos críticos:
- disponibilidade da API;
- integridade dos dados de mobilidade;
- tokens de push/autenticação;
- preferências dos usuários;
- dados colaborativos de localização;
- credenciais de infraestrutura;
- histórico operacional proprietário.

Ameaças prioritárias:
- DDoS e abuso de API;
- scraping massivo;
- credential stuffing;
- BOLA/IDOR;
- injection;
- SSRF;
- supply-chain compromise;
- secrets expostos;
- falsificação de telemetria/crowdsourcing;
- replay;
- acesso indevido ao banco;
- comprometimento de CI/CD.

## 4. Controles de edge
- HTTPS obrigatório;
- TLS moderno;
- Cloudflare/WAF quando disponível;
- rate limiting por IP/device/token/rota;
- bot mitigation;
- limites de payload;
- bloqueio geográfico somente se houver motivo comprovado.

## 5. API
- schema validation estrita;
- allowlists quando aplicável;
- autenticação centralizada;
- autorização por recurso;
- IDs não sequenciais em recursos sensíveis;
- paginação e limites máximos;
- timeouts;
- proteção contra abuso de endpoints caros;
- idempotency keys para operações mutáveis relevantes.

## 6. Mobile
- nenhum segredo estático privilegiado no bundle;
- tokens no armazenamento seguro da plataforma;
- certificate pinning apenas após análise operacional, pois pode aumentar risco de indisponibilidade;
- root/jailbreak detection como sinal, não como único controle;
- minimizar logs locais;
- build de release sem debug endpoints.

## 7. Banco e rede
- PostgreSQL e Redis não expostos à internet;
- firewall default deny;
- usuário de aplicação com privilégios mínimos;
- usuário de migration separado;
- backups criptografados;
- histórico bruto arquivado em domínio de falha externo à VPS;
- checksum SHA-256 e revalidação do objeto remoto antes de apagar partições hot;
- paridade de contagem de linhas hot/archive e bloqueio de exclusão em partições multi-fonte;
- lock transacional comum entre escrita e drop + rechecagem atômica antes da exclusão;
- retenção destrutiva desabilitada por padrão;
- restore testado periodicamente;
- credenciais de object storage e demais segredos fora do Git.

## 8. CI/CD
- branch protection;
- pull requests;
- testes obrigatórios;
- secret scanning;
- dependency scanning;
- SAST;
- geração de SBOM em releases;
- artefatos assinados quando aplicável;
- ambientes separados dev/staging/prod.

## 9. Crowdsourcing
- opt-in explícito;
- pseudonimização;
- score de reputação técnico do sinal, não do “perfil social”;
- detecção de spoofing e velocidade impossível;
- comparação com outros sinais;
- retenção curta de coordenadas brutas;
- agregação antes do uso analítico.

## 10. Resposta a incidentes
Desde o MVP:
- owner do incidente;
- classificação por severidade;
- rotação de credenciais;
- capacidade de revogar tokens;
- logs mínimos necessários para investigação;
- runbook de vazamento/indisponibilidade;
- canal de reporte de vulnerabilidades.

## 11. Critérios de release
Nenhuma release de produção com:
- vulnerabilidade crítica conhecida sem mitigação;
- segredo detectado no repositório;
- teste crítico quebrado;
- migration irreversível sem plano de rollback;
- dependência sem origem identificada.
