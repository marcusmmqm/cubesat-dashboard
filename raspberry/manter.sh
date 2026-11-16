#!/bin/bash
# Uso: manter.sh NOME comando [args...]
# Roda o comando e reabre se ele terminar. Log em ~/.cache/cubesat-kiosk/NOME.log
# Se o próprio manter.sh for encerrado, fecha também o programa que vigia.
nome="$1"; shift
log_dir="$HOME/.cache/cubesat-kiosk"; mkdir -p "$log_dir"
log="$log_dir/$nome.log"
filho=
trap '[ -n "$filho" ] && kill "$filho" 2>/dev/null; exit 0' TERM INT HUP
while true; do
    echo "=== $(date '+%F %T') iniciando: $*" >>"$log"
    "$@" >>"$log" 2>&1 &
    filho=$!
    wait "$filho"; codigo=$?
    filho=
    echo "=== $(date '+%F %T') terminou (código $codigo), reabrindo em 3 s" >>"$log"
    tail -n 2000 "$log" >"$log.tmp" && mv "$log.tmp" "$log"   # log não cresce sem fim
    sleep 3 & wait $!
done
