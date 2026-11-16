"""Vigia da "tela preta" do dashboard Python.

Às vezes a janela do dashboard (Tk, via Xwayland) fica com um retângulo preto
(~704x320) onde o conteúdo não é redesenhado. A causa ainda não foi achada; o
que se sabe é que reabrir o dashboard sempre limpa a tela.

A cada 5 s, se o dashboard estiver na frente, mede a fração de pixels pretos
puros abaixo da barra (o dashboard não tem áreas pretas grandes). Se passar de
20% em duas medições seguidas: registra hora e um print em
~/.cache/cubesat-kiosk/preto/ e reabre só o dashboard (o manter.sh o reabre).
"""
import os
import subprocess
import time

INTERVALO_S = 5
LIMITE = 0.20
DASHBOARD = "python3 dashboard.py --tela-cheia --tcp localhost:5555"
TITULO = "CubeSat · Telemetria LoRa"

pasta = os.path.expanduser("~/.cache/cubesat-kiosk/preto")
os.makedirs(pasta, exist_ok=True)
log = open(os.path.join(pasta, "preto.log"), "a", buffering=1)


def agora():
    return time.strftime("%F %T")


def dashboard_na_frente():
    return subprocess.run(["wlrctl", "toplevel", "find", f"title:{TITULO}", "state:focused"],
                          capture_output=True).returncode == 0


def fracao_preta():
    p = subprocess.run(["grim", "-t", "ppm", "-g", "0,44 800x436", "-"],
                       capture_output=True, timeout=5).stdout
    px = p.split(b"\n", 3)[3]
    amostras = range(0, len(px), 3 * 7)
    pretos = sum(1 for i in amostras if px[i] < 3 and px[i + 1] < 3 and px[i + 2] < 3)
    return pretos / len(amostras), p


log.write(f"{agora()} vigia iniciado\n")
seguidas = 0
while True:
    try:
        if dashboard_na_frente():
            frac, img = fracao_preta()
            seguidas = seguidas + 1 if frac > LIMITE else 0
            if seguidas >= 2:
                hora = time.strftime("%Y%m%d-%H%M%S")
                open(os.path.join(pasta, f"{hora}.ppm"), "wb").write(img)
                pid = subprocess.run(["pgrep", "-u", str(os.getuid()), "-xf", DASHBOARD],
                                     capture_output=True, text=True).stdout.split()
                log.write(f"{agora()} preto={frac:.2f} -> reabrindo o dashboard (pid {pid})\n")
                for p in pid:
                    subprocess.run(["kill", p])
                seguidas = 0
                time.sleep(15)          # dá tempo do dashboard reabrir
        else:
            seguidas = 0
    except Exception as e:  # o vigia nunca deve cair
        log.write(f"{agora()} erro: {e}\n")
    time.sleep(INTERVALO_S)
