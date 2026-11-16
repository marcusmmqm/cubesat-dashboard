#!/bin/bash
# Desfaz o instalar.sh: tira o quiosque CubeSat e volta o EcoDisplay.
# Uso (no Raspberry):  sudo ~/cubesat-kiosk/desinstalar.sh
set -u
[ "$(id -u)" = 0 ] || { echo "rode com sudo"; exit 1; }
systemctl disable --now cubesat-kiosk.service
rm -f /etc/systemd/system/cubesat-kiosk.service /etc/pam.d/cubesat-kiosk
systemctl daemon-reload
systemctl enable --now ecodisplay.service
