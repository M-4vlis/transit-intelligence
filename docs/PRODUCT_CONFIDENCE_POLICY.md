# Política de apresentação do ETA e da confiança

Este documento define o comportamento pretendido, não autoriza exposição no
aplicativo. A API pública continua retornando apenas o contrato experimental
existente até uma decisão manual posterior ao gate do M2.

## Alta confiança

- mostrar o ETA junto de uma janela calibrada;
- evitar linguagem de certeza absoluta;
- retirar o nível se a evidência ficar antiga ou sair dos limites calibrados.

## Média confiança

- priorizar uma janela de chegada em vez de um minuto isolado;
- explicar de forma curta que o trânsito ou a evidência recente ampliam a
  variação;
- não usar a mesma ênfase visual reservada à faixa alta.

## Baixa confiança

- não prometer um minuto exato quando a janela calibrada for ampla demais;
- preferir “previsão instável” ou “aguardando mais dados”;
- manter posição do veículo e horário observado disponíveis sem transformar
  ausência de evidência em falsa precisão.

## Regras comuns

- estado indisponível é um resultado válido;
- nível, janela e motivo devem vir da mesma versão congelada do algoritmo;
- o contrato deve carregar versão, instante de avaliação e códigos de motivo;
- confiança não pode ser inferida no cliente;
- alterações visuais exigem discussão e aprovação do usuário antes de código.
