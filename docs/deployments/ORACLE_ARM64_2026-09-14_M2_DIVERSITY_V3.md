# Oracle ARM64 — M2 diversity audit and candidate v3

Data: 2026-09-14 UTC

Commits implantados: `2dad29d`, `0e24c83`

CI final: <https://github.com/M-4vlis/transit-intelligence/actions/runs/34795671677>

## Resultado

A calibração passou a medir diversidade por faixa de confiança, cobrindo
linha, célula espacial grossa e método do ETA. A célula usa grade de 0,025 grau
e não preserva a coordenada exata da parada.

A primeira coorte schema 2 encontrou boa dispersão de linhas e regiões, mas
100% dos 18 resultados de alta confiança vinham de `vehicle_recent_speed`. O
gate de concentração bloqueou corretamente a calibração.

O candidato `m2-candidate-v3` removeu os pontos concedidos diretamente pelo
nome do método e redistribuiu o peso para suporte amostral normalizado,
dispersão da velocidade e qualidade do casamento. Calibrador e resumo filtram
explicitamente a versão v3; evidência v2 permanece imutável e fora desse
conjunto.

## Primeira coorte v3

- 45 chegadas observadas;
- alta: 10 resultados, MAE 131,145 s;
- média: 33 resultados, MAE 91,718 s e presença dos três métodos;
- baixa: 2 resultados, amostra ainda insuficiente;
- `promotion_authorized=false`;
- nenhuma alteração na API pública ou no aplicativo.

Uma única coorte não justifica reajuste adicional. Os limiares v3 permanecem
shadow até que dias posteriores forneçam evidência independente e holdout.

## Durabilidade e saúde

- restore integral do manifesto M2: 60/60 objetos, 991.088 bytes, status
  `verified`;
- CI: 163 testes aprovados, 9 integrações ignoradas sem dependências reais e
  Ruff aprovado;
- seis serviços em execução; PostgreSQL, Valkey, API, ingestão e edge proxy
  saudáveis;
- API local pronta para banco e cache; leitura pública respondeu HTTP 200;
- fonte oficial ao vivo: 6.296 recebidos/válidos, zero rejeitados e fingerprint
  `b8a3775b7ce4415241a1ba377303da6801f6c089d5c26dac8c370871465c1e33`;
- ingestão posterior: 4.962 recebidos, 3.237 persistidos, 4.414 atualizações de
  cache e zero rejeitados;
- monitor operacional: `passed`, sem avisos;
- filesystem raiz em 46%, com 53 GiB livres; cerca de 10 GiB de memória
  disponível;
- timers de coorte, monitor, perfis, restore, orçamento e retenção verificada
  ativos;
- `.env.production` preservado com SHA-256
  `4135a4a891ea12af518ffdbe46a609010b5f0bedda4ff8650808b5275f981e30`.
