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
  (-180 a +180°) e Vel. angular Azim. (°/s) **com sinal**. O campo 0 do `408A2` aparece na
  tabela como Setpoint_atitude (antes "RefSpeed Roda Reação").

## Comandos enviados (para o firmware)

Cada toque envia **uma linha de texto terminada em `\n`** com o mesmo JSON que o
fluxo mandava antes ao ChirpStack. O campo `data` é Base64 dos bytes do comando.

```
{"devEui": "0005168000136ee4","confirmed": true,"fPort": 1,"data": "AAE="}\n
```

**MauáSat** (`devEui` `0005168000136ee4`) — o botão só escolhe o comando; ele é
enviado depois de **Update** + PIN correto (PIN errado não envia nada):

| Botão | `data` | Bytes |
|---|---|---|
| ACIONA DEPLOYER | `AAE=` | `00 01` |
| DESLIGA DEPLOYER | `AAI=` | `00 02` |
| DESLIGA ATITUDE | `AAQ=` | `00 04` |
| LIGA ATITUDE | ex. `AAUBLA==` | `00 05` + azimute (uint16 big-endian; 300 → `01 2C`) |

O azimute vem do campo **SET AZIMUTE** (digitar e apertar Enter no teclado da
tela). Sem azimute definido, LIGA ATITUDE sai só com `00 05`.

(`confirmed` e `fPort` vêm do formato do ChirpStack e são sempre `true` e `1`.)

## Tela (800x480, rola para baixo, sem rolagem lateral)

Segue as imagens de referência do painel antigo (`ParaSerVisualizado1.png` e
`ParaSerVisualizado2.png`, não incluídas) e `NodeREDAtualizado.png`:

1. **ultimo envio** (s desde o último comando) e **atualizado a** (s desde a
   última mensagem recebida do CubeSat); botões, SET AZIMUTE e Update.
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
