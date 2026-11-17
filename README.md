# CubeSat · Dashboard de telemetria LoRa

Dashboard em Python que lê o receptor LoRa pela porta serial e mostra, em tempo
real, dois painéis lado a lado:

- **Velocidades da roda de reação** (esquerda): gráfico dos últimos 60 s de
  MeasuredSpeed, RefSpeed (`1F864`) e Esforço PID (`408A2`), eixo fixo de -3000
  a +3000. A legenda mostra o valor mais recente de cada série.
- **Atitude** (direita): relógio para acompanhar o posicionamento angular do
  CubeSat:
  - ponteiro **branco, curto** = Setpoint_atitude do `408A2` (ângulo pedido,
    devolvido pelo satélite depois do comando LIGA ATITUDE);
  - ponteiro **vermelho, longo** = posição atual = **angulo do `520B6`** (o
    antigo Azimute satélite do `408A2` virou o campo "x", sem uso por enquanto);
  - mostrador de 30° em 30°, 360° no alto, sentido horário;
  - legenda: setpoint e posição atual de 0 a 359° (qualquer valor da posição
    é convertido: -51 → 309°, 200 → 200°, 370 → 10°), velocidade angular
    (°/s, com sinal) e diferença até o alvo pelo caminho mais curto (-180 a +180°);
  - setpoint fora de 0–359 aparece como "inválido (N)" e não move o ponteiro;
  - cada ponteiro fica cinza quando o seu ID para de chegar por mais de 5 s
    (`408A2` → setpoint; `520B6` → posição), com o aviso "sem 408A2 há X s" /
    "sem 520B6 há X s".

Cada painel tem um botão **Limpar**.

## Raspberry e Node-RED

Na estação de solo com Raspberry Pi (tela de 800x480), o dashboard roda num
quiosque junto com o painel do Node-RED, que cuida do módulo LoRa e envia os
comandos ao CubeSat:

- [`raspberry/`](raspberry/README.md): quiosque (barra de troca de telas,
  serviço, instalação) e uma simulação do CubeSat para testar sem o receptor;
- [`node-red/`](node-red/README.md): gerador do fluxo do Node-RED e o protocolo
  dos comandos enviados pela serial.

## Requisitos

- Python 3.10+ com tkinter (já vem no instalador do Windows; no Ubuntu: `sudo apt install python3-tk`)
- `pyserial`: `pip install -r requirements.txt`
- Receptor LoRa ligado por USB (adaptador FTDI FT231X), 115200 baud

## Uso

```bash
python3 dashboard.py
```

A porta do receptor é detectada sozinha (procura o adaptador FTDI; se não achar,
usa a primeira porta USB). Se o receptor estiver desconectado, o programa espera
e conecta quando ele for plugado.

Opções:

```
--port COM5          força a porta (ex.: COM5 no Windows, /dev/ttyUSB0 no Linux)
--baud 115200        velocidade da serial
--janela 60          segundos mostrados nos gráficos
--tela-cheia         janela do tamanho da tela (usado no Raspberry, tela 800x480)
--tcp HOST:PORTA     recebe as linhas do Node-RED em vez de abrir a serial
```

No Raspberry o dashboard roda com `--tcp localhost:5555`: lá o Node-RED é quem
abre a serial do LoRa (para também enviar comandos ao CubeSat) e repassa cada
linha recebida ao dashboard por essa porta.

No Linux, o usuário precisa estar no grupo `dialout` para abrir a serial.

## Executável para Windows

O executável precisa ser gerado **no próprio Windows** (o PyInstaller não gera
`.exe` a partir do Linux).

1. Instale o Python 3 em <https://www.python.org/downloads/>, marcando
   **"Add python.exe to PATH"**.
2. Baixe este repositório (botão **Code → Download ZIP**) e extraia.
3. Dê dois cliques em **`build_windows.bat`**.

O script instala o PyInstaller e o pyserial, gera `CubeSatDashboard.exe` e copia
para a Área de Trabalho. Depois disso o Python não é mais necessário: basta clicar
no ícone.

Observações:
- O driver do FTDI normalmente é instalado pelo Windows Update. Se o receptor não
  aparecer, instale o driver **VCP** do site da FTDI.
- O Windows Defender às vezes desconfia de executáveis do PyInstaller. Se bloquear:
  **Mais informações → Executar assim mesmo**.
- O `build_windows.bat` ainda não foi testado num Windows.

## Formato das mensagens

O receptor envia uma mensagem CAN por linha:

```
{0001F864:FF86000000000000}
```

(8 dígitos hex de ID, `:`, 8 bytes de dados). O formato antigo com espaços,
`{0001F864 FF 86 00 00 00 00 00 00}`, também é aceito. Linhas com menos ou mais
de 8 bytes são descartadas.

Decodificação usada (nomes e ordem dos campos conforme o mapa CAN novo,
`NovoMapaCANParaAjusteCodigo.png`, e o fluxo do Node-RED de 17/11/2026):

| ID | Campos | Formato |
|---|---|---|
| `1F864` | MeasuredSpeed, RefSpeed, Measured Current, RefTorque | 4 × int16 big-endian com sinal |
| `408A2` | Esforço PID, Setpoint_atitude, x (antigo Azimute satélite, sem uso), Vel. angular Azim. | 4 × 16 bits big-endian: Setpoint_atitude (bytes 2–3) sem sinal (0–359°); Esforço PID (bytes 0–1), x (bytes 4–5) e Vel. angular (°/s) com sinal |
| `520B6` | aux1, aux2, aux3, angulo | 4 × int16 big-endian com sinal: aux1 = bytes 0–1 (antes v_solar_bottom e Yminus), aux2 = 2–3 (Y e Xminus), aux3 = 4–5 (X e top), angulo = 6–7 (posição atual; qualquer valor vira 0–359°) |

![Mapa CAN](mapaCAN2.png)

## Como mudar os gráficos

Tudo fica na lista `CHARTS`, no topo de `dashboard.py`: título, faixa do eixo
(`y=(mínimo, máximo, passo)`), se os valores são com sinal, e as séries
(`(can_id, campo, rótulo, cor)`). Novos IDs entram em `DECODERS`, em `can_parser.py`.

## Testes

```bash
python3 -m unittest
```

## Problemas conhecidos

- **Dados misturados entre IDs (firmware).** Parte dos quadros `1F864`, `520B6`,
  `5F8B4` e `F800` chega com bytes de outros IDs (ex.: `86FF050301020000` = início
  do `1F864` + fim do `520B6`), além de quadros preenchidos pela metade. Isso gera
  os picos nos gráficos. A causa provável é um buffer compartilhado no firmware
  que monta os pacotes LoRa; a correção é um buffer por ID ou copiar ID + 8 bytes
  de forma atômica. `408A2` e `4F8A0` chegam limpos.
- **Ordem dos bytes**: `1F864` é lido como int16 big-endian com sinal. Com o firmware antigo o `1F864` chegava em little-endian (roda parada:
  `7A00` → +122); se aparecerem valores como 31232 com a roda parada, a ordem
  voltou a ser little-endian.
