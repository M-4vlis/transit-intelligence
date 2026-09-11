# Catálogo GTFS versionado

## Importação segura

O comando baixa a fonte oficial com limites de tamanho, valida ZIP, CRC, schema
e SHA-256, grava todas as tabelas em uma transação e ativa o snapshot somente
depois da importação completa:

```bash
./infra/scripts/import_gtfs.sh .env.production
```

Executar sem trocar o snapshot ativo:

```bash
./infra/scripts/import_gtfs.sh .env.production --no-activate
```

Uma segunda execução do mesmo conteúdo é idempotente e não duplica linhas.

## Verificação

```sql
SELECT snapshot_id, status, imported_at, row_counts
FROM transit.gtfs_snapshots
ORDER BY imported_at DESC;
```

Somente uma linha pode ter `status = 'active'`. A API consulta apenas essa
versão.

## Rollback

Escolha um SHA-256 já importado e ative-o atomicamente:

```bash
./infra/scripts/import_gtfs.sh .env.production \
  --activate-snapshot SHA256_DO_SNAPSHOT_ANTERIOR
```

O rollback não apaga o snapshot novo. Retenção de snapshots GTFS fica fora
deste marco e não deve ser automatizada antes de haver política específica.
