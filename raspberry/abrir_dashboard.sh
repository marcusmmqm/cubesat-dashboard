#!/bin/bash
# Abre o dashboard Python na tela do Raspberry. Os dados chegam do Node-RED
# (porta 5555), que é quem cuida da serial do LoRa e envia os comandos.
cd "$HOME/dashboardPython"
exec python3 dashboard.py --tela-cheia --tcp localhost:5555
