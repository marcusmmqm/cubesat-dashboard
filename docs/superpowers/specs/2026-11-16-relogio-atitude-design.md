# Relógio de atitude no dashboard Python

## Intenção

Acompanhar o posicionamento angular do CubeSat: ver se ele chega ao ângulo
pedido e se fica parado ou oscila em torno dele. O painel da direita
("Painéis solares e atitude") é substituído por um relógio.

## O que aparece

- **Relógio sem ponteiro de segundos.** Mostrador marcado de 30° em 30°
  (onde seriam 1 h … 12 h), com 360° no alto; ângulos crescem no sentido horário.
- **Ponteiro das horas, vermelho e curto:** Setpoint_atitude (alvo).
- **Ponteiro dos minutos, branco e longo:** posição angular atual (Azimute satelital).
- **Legenda:**
  - Setpoint_atitude — 0 a 359°
  - Posição atual — 0 a 359°
  - Velocidade angular — °/s
  - Diferença — quanto falta do atual ao alvo pelo caminho mais curto, -180 a +180°
- **Dado parado:** se o `408A2` não chegar por mais de 5 s, a legenda mostra
  "sem dados há X s" e os ponteiros ficam acinzentados.
- **Valor inválido:** setpoint fora de 0–359 ou posição fora de -180–+180 não
  move o ponteiro; a legenda mostra "inválido (N)".
- Correção posterior: a posição chega com sinal (65485 do satélite real = -51°).

Sem rastro, gráfico de desvio ou contador de voltas (decidido: a oscilação se vê
no movimento do ponteiro).

## Dados

Tudo vem do CAN `408A2`, pelo LoRa, 4 campos de 16 bits big-endian:

| Campo | Nome | Leitura |
|---|---|---|
| 0 | Setpoint_atitude (era "RefSpeed Roda Reação") | sem sinal, 0–359° |
| 1 | Esforço PID | com sinal (como hoje) |
| 2 | Azimute satelital (posição atual) | **com sinal**, -180 a +180°; mostrado de 0 a 359° (-51 → 309°) |
| 3 | Vel. angular Azim. | com sinal, °/s (negativa = anti-horário) |

O Setpoint_atitude é o valor que o satélite devolve depois de receber o comando
LIGA ATITUDE do Node-RED: se o ponteiro vermelho não vai ao ângulo enviado, o
comando não chegou.

## Outras mudanças

- Gráfico da esquerda: sai o Setpoint_atitude (era a série "RefSpeed Roda
  Reação"); ficam MeasuredSpeed, RefSpeed e Esforço PID.
- `can_parser.py`: `408A2` passa a ter leitura por campo (sem sinal / com sinal).
- Node-RED do Raspberry: tabela do `408A2` com a mesma leitura e o campo 0
  chamado Setpoint_atitude. (O fluxo novo com "Send Setpoint_atitude (int 0 a
  359°)" visto em NodeREDAtualizado.png não está na pasta; quando estiver, o
  fluxo do Raspberry passa a ser gerado a partir dele.)

## Restrições

- Mesma tecnologia do resto: desenhado no Canvas do Tk, no mesmo ritmo de
  redesenho (25 quadros/s), sem dependência nova.
- Tem que caber na tela de 800x480 do Raspberry (modo compacto) e funcionar na
  janela grande do PC.
- O ponteiro só se move quando chega um `408A2`; não há suavização entre leituras.

## Abordagens consideradas

- **Canvas do Tk (escolhida):** igual aos gráficos atuais, leve no Raspberry.
- Biblioteca de gráficos (matplotlib): dependência nova e pesada, visual
  diferente do resto.

## A cargo de quem implementar

Tamanhos e espessuras dos ponteiros, fontes e posição da legenda no modo compacto.
