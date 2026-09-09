# Rio realtime — evidências e contrato de borda (01/09/2026)

## Fonte primária configurada
Endpoint oficial informado em documentação pública da Prefeitura:

`https://dados.mobilidade.rio/gps/sppo`

A SMTR mantém documentação do histórico `gps_onibus` com campos como `timestamp_gps`, `id_veiculo`, `servico`, `latitude`, `longitude`, `flag_em_movimento`, `tipo_parada`, `velocidade_instantanea`, `velocidade_estimada_10_min`, `distancia` e `versao`.

## Evidência de schema drift
Em 07/08/2026, issue pública do repositório `RJ-SMTR/pipelines_v3` registrou incidente no monitoramento realtime após alteração de **campos e tipos** da API `dados.mobilidade.rio/gps/sppo`.

Consequência arquitetural: o schema externo nunca é tratado como contrato interno. O Rio Adapter aceita aliases conhecidos, ignora extras, põe registros inválidos em quarentena e gera fingerprint dos campos observados por lote.

## Evidência do código aberto da própria SMTR
O repositório público `RJ-SMTR/mobilidade-rio-api` documenta o endpoint SPPO, os parâmetros `dataInicial`/`dataFinal`, a equivalência histórica `id_veiculo = ordem` e o envelope de erro de aplicação `RetornoOK=false`. Seus testes antigos também registram a família de campos `ordem`, `latitude`, `longitude`, `datahora`, `velocidade`, `linha`, `datahoraenvio` e `datahoraservidor`.

O adapter mantém compatibilidade com essa família legada e com a família documentada mais recente (`id_veiculo`, `servico`, `timestamp_gps`, etc.), incluindo coerção defensiva de identificadores numéricos e timestamps epoch em segundos/milisegundos.

## Fixture de contract test
`backend/tests/fixtures/rio_gps_current.json` representa o conjunto de campos documentado oficialmente e serve para garantir compatibilidade do adapter com a família de schema atual.

**Importante:** essa fixture ainda não é uma captura live do endpoint em 01/09/2026. O runtime atual não permite abrir diretamente a origem. Foi adicionado um workflow `Rio source contract smoke`, executado a cada 6 horas assim que o repositório estiver no GitHub, para produzir o primeiro fingerprint real e evidenciar regressões futuras.

## Referências
- Prefeitura do Rio / SMTR — API realtime SPPO: `https://dados.mobilidade.rio/gps/sppo`
- Metadata Data.Rio / histórico GPS SPPO: `https://github.com/prefeitura-rio/queries-datario/blob/master/metadata.json`
- Documentação de apuração SMTR: `https://rj-smtr.github.io/pipelines-docs/pipelines/listagem_pipelines/monitoramento/apuracao_viagens_v10/`
- Incidente de schema em 07/08/2026: `https://github.com/RJ-SMTR/pipelines_v3/issues/492`

- Código aberto SMTR / utilitário SPPO: `https://github.com/RJ-SMTR/mobilidade-rio-api`
