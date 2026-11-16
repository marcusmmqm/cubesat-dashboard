#!/bin/bash
# Simulação de envio de dados do CubeSat, para ver o quiosque funcionando sem o
# receptor LoRa. Troca a porta serial do Node-RED para a serial virtual da
# simulação e, ao terminar, devolve o fluxo original (porta real).
#
# Uso (no Raspberry):  ~/cubesat-kiosk/simulacao/simular.sh [minutos]   (padrão: 15)
# Parar antes:         touch /tmp/parar-simulacao
set -u
DIR="$(cd "$(dirname "$0")" && pwd)"
MIN="${1:-15}"
LOG=/tmp/simulacao.log
ORIG=/tmp/simulacao-fluxo-original.json
rm -f /tmp/parar-simulacao

curl -sf localhost:1880/flows -o "$ORIG" || { echo "Node-RED não respondeu"; exit 1; }
deploy() { curl -s -X POST localhost:1880/flows -H "Content-Type: application/json" \
             -H "Node-RED-Deployment-Type: full" --data @"$1" >/dev/null; }

python3 "$DIR/lora_simulado.py" >>"$LOG" 2>&1 &
SIM=$!
restaura() {
    kill "$SIM" 2>/dev/null
    deploy "$ORIG"
    rm -f /tmp/ttyLORA /tmp/simulacao-fluxo-teste.json /tmp/parar-simulacao
    echo "$(date +%T) simulação encerrada, Node-RED de volta à porta real" >>"$LOG"
}
trap restaura EXIT
trap 'exit 0' INT TERM HUP

sleep 1
python3 - "$ORIG" <<'PY'
import json, sys
fluxo = json.load(open(sys.argv[1]))
for n in fluxo:
    if n.get("type") == "serial-port":
        n["serialport"] = "/tmp/ttyLORA"
json.dump(fluxo, open("/tmp/simulacao-fluxo-teste.json", "w"))
PY
deploy /tmp/simulacao-fluxo-teste.json
echo "$(date +%T) simulação iniciada por $MIN min" >>"$LOG"

fim=$(( $(date +%s) + MIN * 60 ))
while [ "$(date +%s)" -lt "$fim" ] && [ ! -e /tmp/parar-simulacao ] && kill -0 "$SIM" 2>/dev/null; do
    sleep 1
done
