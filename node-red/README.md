# Node-RED do Raspberry · comandos ao CubeSat pelo LoRa (FTDI)

O fluxo do Raspberry (`fluxoCubesat-rasp.json`) é gerado a partir do fluxo
original (`fluxoCubesatNODE.txt`) e do `codec1.txt` (de onde vem o
`CUBESATProtocolParser`). **Esses dois não estão no repositório** (o primeiro
tem a chave secreta do Supabase; o segundo é de outro projeto): para gerar de
novo, coloque-os nesta pasta — o `.gitignore` os mantém fora do git.

```bash
python3 gerar_fluxo_rasp.py                     # porta /dev/ttyUSB0
python3 gerar_fluxo_rasp.py --porta /dev/ttyUSB1  # outra porta
```

e carregado no Node-RED do Raspberry pela API (não precisa de sudo):

```bash
scp fluxoCubesat-rasp.json pi@10.33.133.150:/tmp/
ssh pi@10.33.133.150 'curl -s -X POST localhost:1880/flows \
  -H "Content-Type: application/json" -H "Node-RED-Deployment-Type: full" \
  --data @/tmp/fluxoCubesat-rasp.json'
```

O `codec1.txt` (aba "Agro") é de outro projeto e não é carregado.

## Serial do módulo LoRa

- Porta `/dev/ttyUSB0` (adaptador FTDI), **115200 baud, 8N1**.
- O Node-RED é o único programa que abre a porta: recebe e envia.
- Cada linha recebida é repassada ao dashboard Python pela porta TCP **5555**
  (`dashboard.py --tcp localhost:5555`).
- Cada linha CAN recebida (`{0001F864:...}`) é decodificada pelo mesmo
  `CUBESATProtocolParser` do `codec1.txt` (copiado de lá pelo gerador) e entra no
  fluxo como se viesse do ChirpStack pela porta 250. Linhas de texto (ex.
  "Mauasat online Compiled on ...") entram como a porta 251.
- Mesma leitura do dashboard Python: `1F864` com sinal; no `408A2`,
  Setpoint_atitude **sem sinal** (0 a 359°); Esforço PID, Azimute satelital
  (-180 a +180°) e Vel. angular Azim. (°/s) **com sinal**. Ordem do `408A2` no mapa
  CAN novo: Esforço PID (bytes 0–1), Setpoint_atitude (2–3), Azimute (4–5),
  Vel. angular (6–7).
- **Diferença em relação ao dashboard Python:** a tabela do Node-RED ainda lê o
  `520B6` byte a byte (6 painéis e "angulo" = só o byte 6). O dashboard lê
  aux1, aux2, aux3 e angulo como 4 × int16 com sinal; um angulo negativo
  (ex. -51 = `FF CD`) aparece na tabela do Node-RED como 255.

## Comandos enviados (para o firmware)

As mensagens vêm do **`../comandos.txt`**, o mesmo arquivo do dashboard Python:
o gerador as copia para dentro do fluxo. **Depois de mudar o `comandos.txt`,
rode `raspberry/enviar_para_rasp.sh`** (gera o fluxo de novo e carrega no
Node-RED). Cada mensagem sai numa linha terminada em `\r\n`; `{SETPOINT}` vira
o setpoint em hex, 4 dígitos (300 → `012C`).

**Botões do painel** (MauáSat): o botão só escolhe o comando; ele é enviado
depois de **Update** + PIN correto (PIN errado não envia nada). Por dentro, os
botões ainda montam o JSON do ChirpStack, e o nó "Enviar pelo LoRa" troca pela
mensagem do `comandos.txt`:

| Botão | Bytes no JSON | Mensagem |
|---|---|---|
| LIGA ATITUDE | `00 05` + setpoint | `LIGA_ATITUDE` (hoje `{00002004:80SSSS0000000000}`) |
| DESLIGA ATITUDE | `00 04` | `DESLIGA_ATITUDE` (hoje `{00002004:00SSSS0000000000}`) |
| ACIONA DEPLOYER | `00 01` | `ACIONA_DEPLOYER` (hoje vazia: não envia) |
| DESLIGA DEPLOYER | `00 02` | `DESLIGA_DEPLOYER` (hoje vazia: não envia) |

O setpoint vem do campo **Send Setpoint_atitude** (digitar e apertar Enter).
Sem setpoint válido, LIGA ATITUDE **não é enviado**; DESLIGA usa o último
setpoint digitado, ou 16 se não houver. Mensagem vazia ou comando desconhecido:
nada é enviado e "Último comando" mostra "NÃO enviado" com o motivo.

**Dashboard Python**: manda as mesmas linhas pela porta TCP 5555 (a conexão
pela qual ele recebe a telemetria). O Node-RED só aceita conexões do próprio
Raspberry (`127.0.0.1`) e só linhas iguais a uma das mensagens do
`comandos.txt` (setpoint de 0 a 359); o resto é ignorado (aviso no log do
Node-RED). Estes não pedem PIN.

## Tela (800x480, rola para baixo, sem rolagem lateral)

Segue as imagens de referência do painel antigo (`ParaSerVisualizado1.png` e
`ParaSerVisualizado2.png`, não incluídas) e `NodeREDAtualizado.png`:

1. **ultimo envio** (s desde o último comando) e **atualizado a** (s desde a
   última mensagem recebida do CubeSat); botões, Send Setpoint_atitude e Update.
2. **V BATERIA** e **Temperatura** (EPS `5F8B4`) com gráficos das últimas 2 h;
   mensagem de texto do satélite ("Mauasat online ...").
3. Tabela EPS/OBD/BLDC/ACS/TTC, lista das últimas 10 mensagens ADS-B e o mapa
   da trajetória.
4. Rádio LoRa: estado da serial e último comando enviado.

Tabela, mostradores e gráficos são atualizados no máximo a cada 2 s (com o dado
mais recente): pela serial chegam dezenas de quadros por segundo, e o fluxo
antigo foi feito para uma mensagem a cada poucos minutos.

O **mapa** vem de `https://mediaserver.maua.br/cubesat/latestTrajectory` e só
aparece com internet (sem rede: "mapa indisponível sem internet"); é recarregado
a cada 60 s. O Raspberry não envia nada ao Supabase, então a trajetória vem do
que outras estações enviarem. O mostrador "Gateway movel" não existe aqui (não há
gateway com o LoRa ligado direto).

## O que muda em relação ao fluxo original

- MQTT (ChirpStack) desativado e envio ADS-B ao Supabase retirado (os nós
  `ADBS` tinham a chave secreta do Supabase em texto puro): nada sai do Raspberry.
- Grupo "TCC Samuel" removido, com os nós que só serviam a ele.
- O botão ENVIA3 do MauáSat continua desativado, como no original.
- A janela de PIN abre já no primeiro toque em Update (o original ignorava o
  primeiro, para não abrir sozinha ao recarregar a página).
- Nós `decode`/`encode` (pacote `node-red-contrib-crypto-js`) trocados por nós
  `function` equivalentes.
- Tema escuro com as cores do dashboard Python.
