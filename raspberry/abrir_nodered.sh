#!/bin/bash
# Abre o painel do Node-RED no Chromium, como aplicativo (sem abas nem barra de endereço).
URL="http://localhost:1880/ui/"
# espera o Node-RED ficar pronto (no boot ele demora alguns segundos)
until curl -sf -o /dev/null "$URL"; do sleep 2; done
exec chromium \
    --app="$URL" \
    --user-data-dir="$HOME/.config/cubesat-chromium" \
    --ozone-platform=wayland \
    --enable-wayland-ime --wayland-text-input-version=3 \
    --start-maximized \
    --no-first-run --noerrdialogs --disable-infobars \
    --disable-session-crashed-bubble --hide-crash-restore-bubble \
    --disable-features=Translate \
    --disable-pinch --overscroll-history-navigation=0 \
    --password-store=basic \
    --check-for-update-interval=31536000
