#!/bin/bash
# Instala o quiosque CubeSat no lugar do EcoDisplay.
# Uso (no Raspberry):  sudo ~/cubesat-kiosk/instalar.sh
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "rode com sudo"; exit 1; }
K="$(cd "$(dirname "$0")" && pwd)"

echo "== pacote wlrctl (troca de janelas)"
apt-get install -y wlrctl

echo "== sessão e serviço"
install -m 644 "$K/pam-cubesat-kiosk" /etc/pam.d/cubesat-kiosk
install -m 644 "$K/cubesat-kiosk.service" /etc/systemd/system/cubesat-kiosk.service
systemctl daemon-reload

echo "== desligando o EcoDisplay (os arquivos dele continuam em ~/EcoDisplay)"
systemctl disable --now ecodisplay.service || true

echo "== ligando o quiosque"
systemctl enable --now cubesat-kiosk.service
sleep 3
systemctl --no-pager status cubesat-kiosk.service | head -12
