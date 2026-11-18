#!/bin/bash
# Sobe tudo para o Raspberry: quiosque, dashboard Python e fluxo do Node-RED.
# Rodar no PC (Linux), de qualquer pasta. Precisa de ssh sem senha para o pi.
#
# Uso:  raspberry/enviar_para_rasp.sh [pi@10.33.133.150]
#
# Antes de trocar o fluxo, guarda o que estava no Node-RED em
# ~/fluxo-backup/AAAA-MM-DD_HHMMSS.json no Raspberry. Para voltar a ele:
#   ssh pi@10.33.133.150 'curl -X POST localhost:1880/flows \
#     -H "Content-Type: application/json" -H "Node-RED-Deployment-Type: full" \
#     --data @fluxo-backup/<arquivo>.json'
set -euo pipefail
RASP="${1:-pi@10.33.133.150}"
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
cd "$RAIZ"

echo "== testes"
python3 -m unittest -q 2>&1 | tail -1

echo "== fluxo do Node-RED"
if [ -f node-red/fluxoCubesatNODE.txt ] && [ -f node-red/codec1.txt ]; then
    python3 node-red/gerar_fluxo_rasp.py
else
    echo "AVISO: sem o fluxo base (node-red/fluxoCubesatNODE.txt e codec1.txt), o fluxo"
    echo "       não é gerado de novo: os botões do Node-RED ficam com as mensagens do"
    echo "       fluxoCubesat-rasp.json já gerado, não com as do comandos.txt atual"
fi
if grep -q "sb_secret" node-red/fluxoCubesat-rasp.json; then
    echo "ERRO: o fluxo gerado tem a chave do Supabase; nada foi enviado"; exit 1
fi

echo "== quiosque -> ~/cubesat-kiosk"
rsync -a --exclude __pycache__ raspberry/ "$RASP:cubesat-kiosk/"

echo "== dashboard Python -> ~/dashboardPython"
rsync -a --exclude .git --exclude .superpowers --exclude __pycache__ \
      --exclude raspberry --exclude node-red --exclude docs --exclude '*.exe' \
      ./ "$RASP:dashboardPython/"

echo "== fluxo -> Node-RED (backup do atual em ~/fluxo-backup)"
scp -q node-red/fluxoCubesat-rasp.json "$RASP:/tmp/fluxoCubesat-rasp.json"
ssh "$RASP" 'set -e
    mkdir -p ~/fluxo-backup
    curl -sf localhost:1880/flows -o ~/fluxo-backup/$(date +%F_%H%M%S).json
    curl -sf -X POST localhost:1880/flows -H "Content-Type: application/json" \
         -H "Node-RED-Deployment-Type: full" --data @/tmp/fluxoCubesat-rasp.json \
         -o /dev/null -w "Node-RED: HTTP %{http_code}\n"
    rm -f /tmp/fluxoCubesat-rasp.json'

echo "== reabrindo o dashboard (o vigia do quiosque reabre em 3 s)"
# [d]: o padrão não casa com a própria linha de comando desta sessão ssh
ssh "$RASP" 'pkill -f "[d]ashboard.py --tela-cheia" || true'

echo "pronto"
