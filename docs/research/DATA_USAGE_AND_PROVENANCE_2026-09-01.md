# Uso de dados e proveniência — triagem inicial

Data: 01/09/2026.

> Triagem de produto/engenharia. Não substitui análise jurídica de propriedade intelectual, termos de uso ou proteção de dados.

## Base pública
O Portal da Transparência da Prefeitura do Rio descreve dados abertos como dados que podem ser acessados, utilizados, modificados e compartilhados livremente para qualquer finalidade, sujeitos no máximo a exigências de preservação da proveniência e da abertura.

Referência oficial: https://transparencia.prefeitura.rio/dados-abertos/

## Decisão de engenharia
Mesmo antes da análise jurídica final, o produto preservará proveniência de toda informação externa. O domínio já mantém `source` e `agency_id`; versões futuras de feeds estáticos manterão `feed_version`/hash e timestamps de captura.

Não removeremos atribuição nem apresentaremos dados municipais brutos como se fossem produzidos pelo produto. Previsões, scores e inferências próprias deverão ser distinguíveis dos dados-fonte.

## Pendências antes do lançamento comercial
1. confirmar termos/licença específicos do endpoint GPS e dos feeds GTFS utilizados;
2. documentar eventual obrigação de atribuição;
3. confirmar rate limits e política aceitável de polling;
4. manter registro da versão/data dos termos consultados;
5. revisar política de privacidade do produto separadamente, especialmente antes de qualquer tratamento de localização do usuário.

## Regra operacional
A coleta 24x7 pode ser tecnicamente preparada, mas a liberação para produção pública/comercial exige que as pendências acima estejam registradas e aprovadas no checklist de release.
