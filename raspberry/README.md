# CubeSat · quiosque do Raspberry

O Raspberry liga direto numa tela de operação, sem terminal e sem internet:

```
┌──────────────────────────────────────────────────────────┐
│ [ Telemetria LoRa ]  [ Node-RED ]           [ Desligar ] │  ← barra (44 px)
├──────────────────────────────────────────────────────────┤
│                                                          │
│   tela escolhida (dashboard Python ou painel Node-RED)   │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

- **Telemetria LoRa**: o `dashboardPython` (gráficos rápidos, lê o receptor LoRa pela serial FTDI).
- **Node-RED**: o painel do Node-RED (`http://localhost:1880/ui/`) aberto no Chromium.
- **Desligar**: pede confirmação e desliga o Raspberry com segurança.

Os dois programas ficam abertos o tempo todo: trocar de tela é instantâneo e os
gráficos não perdem o histórico. Se algum fechar ou travar, reabre sozinho em 3 s.
No boot, o dashboard fica na frente.

## Como funciona

| Peça | O quê |
|---|---|
| `cubesat-kiosk.service` | serviço do systemd que, no boot, abre o compositor gráfico `labwc` na tela do Raspberry como usuário `pi` (sem desktop) |
| `labwc/rc.xml` | reserva o topo para a barra e maximiza as outras janelas abaixo dela, sem barra de título; toque mapeado na tela DSI |
| `labwc/autostart` | abre a barra, o dashboard, o Chromium e o teclado virtual (`squeekboard`), cada um vigiado por `manter.sh` |
| `barra.py` | a barra de troca (Tkinter); troca a janela da frente com `wlrctl` |
| `abrir_nodered.sh` | espera o Node-RED responder e abre o painel no Chromium como aplicativo |
| `abrir_dashboard.sh` | abre o dashboard Python recebendo os dados do Node-RED (`--tcp localhost:5555`) |
| `vigia_tela.py` | vigia da "tela preta" (ver abaixo) |
| `enviar_para_rasp.sh` | roda no PC: sobe quiosque, dashboard e fluxo do Node-RED para o Raspberry |
| `instalar.sh` / `desinstalar.sh` | instala o quiosque no lugar do EcoDisplay / desfaz e volta o EcoDisplay |

Logs de cada programa: `~/.cache/cubesat-kiosk/*.log` no Raspberry; do compositor:
`journalctl -u cubesat-kiosk`.

## Instalar / atualizar

No PC (Linux, com ssh sem senha para o `pi`):

```bash
raspberry/enviar_para_rasp.sh            # ou: raspberry/enviar_para_rasp.sh pi@OUTRO_IP
```

O script roda os testes, gera o fluxo do Node-RED (se o fluxo base estiver em
`node-red/`), copia o quiosque para `~/cubesat-kiosk` e o dashboard para
`~/dashboardPython`, carrega o fluxo no Node-RED (guardando o anterior em
`~/fluxo-backup/` no Raspberry) e reabre o dashboard.

No Raspberry (só na primeira instalação):

```bash
sudo ~/cubesat-kiosk/instalar.sh
```

Depois de atualizar arquivos, `sudo systemctl restart cubesat-kiosk` recarrega a tela.
Sem sudo, dá o mesmo resultado encerrar o compositor (ele volta sozinho):
`kill $(systemctl show -p MainPID --value cubesat-kiosk)`. Para mudar só o comando
do dashboard ou do Chromium, basta editar `abrir_dashboard.sh` / `abrir_nodered.sh`
e fechar o programa: o vigia reabre com o script novo.

Para voltar ao EcoDisplay: `sudo ~/cubesat-kiosk/desinstalar.sh`.

## Node-RED e o rádio

```
receptor LoRa (FTDI, /dev/ttyUSB0, 115200)
        │  ▲
 linhas │  │ comandos dos botões (mensagens do comandos.txt + \r\n)
        ▼  │
     Node-RED ◀─── porta TCP 5555 ───▶ dashboard Python (--tcp localhost:5555)
                linhas ▶ · ◀ botões do dashboard (só de 127.0.0.1)
        │
        └── painel CubeSat no Chromium (http://localhost:1880/ui/)
```

- Pacote de painel: `node-red-dashboard` 3.6.6 (o que os nós `ui_*` dos fluxos usam).
- Fluxo e protocolo dos comandos: ver `../node-red/README.md`.

## Tela preta no dashboard (problema conhecido)

Às vezes a janela do dashboard Python fica com um retângulo preto (~704x320)
no meio. O que se sabe:

- é conteúdo perdido da própria janela do dashboard (Tk roda via Xwayland), não
  do compositor; reabrir o dashboard sempre limpa;
- aconteceu duas vezes, ambas em sessões em que o Chromium foi fechado/reaberto
  e o teclado virtual foi usado; a sequência exata que dispara não foi achada;
- não ajudaram (testado e desfeito): tamanho fixo em vez de maximizado,
  Xwayland com `-shm`.

Contenção: `vigia_tela.py` verifica a cada 5 s; se achar preto no dashboard em
duas verificações seguidas, reabre só o dashboard (perde o histórico de 60 s dos
gráficos). Cada ocorrência fica em `~/.cache/cubesat-kiosk/preto/preto.log`, com
um print (`.ppm`) — use para achar o gatilho.
