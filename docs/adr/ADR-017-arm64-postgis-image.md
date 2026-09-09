# ADR-017 — Imagem PostGIS própria e multi-arquitetura

**Status:** Aceito
**Data:** 2026-09-01

## Contexto

A VPS Oracle usada como runtime inicial é AArch64/ARM64. A imagem oficial `postgis/postgis:17-3.5` usada na fundação inicial publica apenas `linux/amd64`, portanto não é uma base válida para produção nessa máquina.

## Decisão

Construir a imagem de banco do projeto a partir de `postgres:17.11-trixie` (Docker Official Image), instalando `postgresql-17-postgis-3` e `postgresql-17-postgis-3-scripts` pelos repositórios de pacotes assinados disponíveis na imagem/base Debian.

O CI deverá construir a imagem para `linux/amd64` e `linux/arm64` usando Buildx/QEMU antes de aceitar mudanças na imagem do banco.

## Consequências

- não dependemos de uma imagem PostGIS comunitária para ARM64;
- a cadeia de confiança fica limitada ao PostgreSQL oficial + pacotes Debian/PGDG;
- o Dockerfile do banco passa a ser parte crítica do projeto e deve ser revisado como infraestrutura;
- digests de imagens deverão ser congelados antes do primeiro release público.
