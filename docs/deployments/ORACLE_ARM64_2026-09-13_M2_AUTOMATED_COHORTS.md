# Oracle ARM64 — coortes automáticas do M2 — 2026-09-13

## Resultado

A coleta read-only do Confidence Score foi instalada como timer persistente na
VPS ARM64. Ela executa oito vezes ao dia, sobrevive a reinicializações e não
exige intervenção do usuário.

## Controles preservados

- `.env.production` permaneceu com SHA-256
  `800e640768673f08f3190719d868fbb8e5df3412508e91307776c4ddd384570a`;
- `DESTRUCTIVE_RETENTION_ENABLED=false`;
- nenhum container do stack foi reiniciado;
- PostgreSQL, Valkey, API, ingestion, edge proxy e tunnel permaneceram ativos;
- todos os containers apresentaram `RestartCount=0` após a instalação;
- replay limitado a 35% de uma CPU e 768 MiB, com baixa prioridade de CPU/I/O.

## Primeira execução

- unidade: `transit-intelligence-eta-confidence-cohort.service`;
- resultado: `success`, exit code `0`;
- duração observada: 7 segundos;
- relatórios anteriores importados: 7;
- coortes após a execução: 8;
- chegadas observadas acumuladas: 550;
- espaço ocupado: 48 KiB;
- checksums: todos aprovados com `sha256sum -c`.

No agregado inicial, 4 de 8 coortes foram monotônicas. O candidato permanece
`uncalibrated` e não está exposto ao passageiro.

## Diagnóstico paralelo implantado

O replay passou a segmentar viés, cobertura e cauda de erro por método de ETA,
tipo de casamento e linha, além de medir as distâncias de projeção excluídas. A
primeira execução com esse diagnóstico elevou o conjunto para 9 coortes e 576
chegadas observadas.

Nesse lote, houve 26 chegadas observáveis, MAE de 41,19 segundos e um erro acima
de cinco minutos. Das 200 âncoras, 124 foram excluídas como `vehicle_off_shape`;
a distância de projeção teve mediana de 1.331 metros e P90 de 7.206 metros. Isso
indica problema de correspondência entre posição e shape, e não justifica elevar
o limite atual de 250 metros sem investigar rota, sentido e versão do GTFS.

A auditoria seguinte confirmou que o ZIP oficial disponível em 13 de setembro
tem o mesmo SHA-256 do snapshot ativo. Também foi removido um viés do replay que
limitava a amostra depois de ordenar os identificadores de veículo. A primeira
coorte com amostragem determinística distribuída encontrou 43 chegadas em 200
âncoras, contra 26 no lote anterior. Ainda houve 94 exclusões off-shape, agora
com mediana de 2.353 metros; portanto, o problema não era apenas o viés de
seleção.

O resumo passou a contar para os gates somente coortes do método atual. No
primeiro marco havia um dia independente, apenas a faixa noturna e 10/26/7
resultados nas bandas alta/média/baixa. Nenhum gate de cobertura foi considerado
concluído.

Uma coorte noturna adicional mediu a velocidade dos 94 veículos off-shape: 77
(81,9%) estavam abaixo de 0,5 m/s, com velocidade mediana zero. A evidência é
compatível com veículos parados em garagem ou terminal enquanto ainda carregam
a última associação de linha. O limite geométrico permaneceu inalterado; coortes
diurnas serão usadas para confirmar se o padrão desaparece durante a operação.

Ao fim desta etapa havia 11 coortes, 650 chegadas observadas e 96 KiB de
artefatos. Somente 2 coortes, ambas noturnas e do mesmo dia local, usam a nova
amostragem e contam para os gates de calibração.

## Fonte ao vivo durante a mudança

O ingestion worker continuou recebendo HTTP 200 da fonte oficial do Rio. Um lote
posterior à instalação recebeu 2.805 registros, rejeitou zero, persistiu 1.786 e
atualizou 2.410 entradas de cache. O fingerprint observado foi
`b8a3775b7ce4415241a1ba377303da6801f6c089d5c26dac8c370871465c1e33`.

## Acompanhamento

Revisões programadas após 7, 14 e 30 dias. A coleta permanece ativa além desses
marcos até a conclusão da calibração, salvo interrupção operacional explícita.
