"""CubeSat simulado do outro lado do módulo LoRa (porta serial virtual).

Cria /tmp/ttyLORA (pty) e manda, como o receptor LoRa real, uma mensagem CAN por
linha. Simula a atitude: o satélite gira até o Setpoint_atitude com um controle
PD um pouco subamortecido (oscila antes de parar).

- Lê os comandos que o Node-RED envia pela serial (o JSON do ChirpStack):
  LIGA ATITUDE (00 05 + azimute) -> novo setpoint e controle ligado;
  DESLIGA ATITUDE (00 04) -> controle desligado (gira solto, perdendo velocidade).
- Sem comando recente, o setpoint muda sozinho a cada 45 s.
- Uma vez a cada 2 min, o 408A2 some por 7 s (para ver "sem dados"); a posição
  atual continua chegando pelo angulo do 520B6.

Uso: python3 lora_simulado.py
"""
import base64
import json
import math
import os
import pty
import random
import select
import time
import tty

DT = 0.1                                  # 10 quadros de atitude por segundo
SETPOINTS_AUTO = [15, 120, 300, 180, 200]
TROCA_AUTO_S = 45
KP, KD, ACEL_MAX = 0.6, 0.5, 30.0         # PD subamortecido; aceleração máx. em °/s²

ADSB = ["8DE47FA85855303180133D3E6674", "8DE47FA8990CB2A4F0F02086B7F2",
        "8DE80460990D019C105021C35486", "8DE804605853A0340E02BE6CD08E",
        "8DE47FA8990CB1A4D0F81F4839A9", "8DE80460990D029C3050218337FD",
        "8DE80460585514760C444764BAC4", "8DE80460990D039C5050214FB948",
        "8DE4A559EA34D8652B3C00BF61AF", "8DE4A5499915109910C01C52DE56"]


def u16(v):
    return f"{int(round(v)) & 0xFFFF:04X}"


def diff(alvo, atual):
    return (alvo - atual + 180) % 360 - 180


def main():
    m, s = pty.openpty()
    tty.setraw(s)
    try:
        os.unlink("/tmp/ttyLORA")
    except FileNotFoundError:
        pass
    os.symlink(os.ttyname(s), "/tmp/ttyLORA")

    def manda(linha):
        os.write(m, (linha + "\r\n").encode())

    def frame(can_id, dados_hex):
        manda(f"{{{can_id:08X}:{dados_hex}}}")

    theta, omega = 40.0, 0.0              # posição (°, sem limite) e velocidade (°/s)
    setpoint, controle = SETPOINTS_AUTO[0], True
    ultimo_cmd = -1e9
    medida = 0.0                          # velocidade medida da roda (segue a referência)
    t0 = time.time()
    prox_auto, i_auto = t0 + TROCA_AUTO_S, 0
    prox_outros = prox_adsb = prox_txt = t0
    a_adsb, buf = 0, b""

    while True:
        agora = time.time()
        t = agora - t0

        # ---- comandos vindos do Node-RED
        while select.select([m], [], [], 0)[0]:
            buf += os.read(m, 4096)
        while b"\n" in buf:
            linha, buf = buf.split(b"\n", 1)
            try:
                dados = base64.b64decode(json.loads(linha)["data"])
            except (ValueError, KeyError, TypeError):
                continue
            if dados[:2] == b"\x00\x05":
                if len(dados) >= 4:
                    setpoint = (dados[2] << 8 | dados[3]) % 360
                controle, ultimo_cmd = True, agora
                print(f"{time.strftime('%T')} LIGA ATITUDE -> setpoint {setpoint}°", flush=True)
            elif dados[:2] == b"\x00\x04":
                controle, ultimo_cmd = False, agora
                print(f"{time.strftime('%T')} DESLIGA ATITUDE", flush=True)

        # ---- setpoint automático (se ninguém comandou nos últimos 2 min)
        if agora >= prox_auto:
            if agora - ultimo_cmd > 120:
                i_auto = (i_auto + 1) % len(SETPOINTS_AUTO)
                setpoint, controle = SETPOINTS_AUTO[i_auto], True
            prox_auto = agora + TROCA_AUTO_S

        # ---- dinâmica da atitude
        erro = diff(setpoint, theta % 360)
        if controle:
            acel = max(-ACEL_MAX, min(ACEL_MAX, KP * erro - KD * omega))
        else:
            acel = -0.05 * omega          # sem controle: perde velocidade devagar
        acel += random.gauss(0, 0.3)      # perturbação
        omega += acel * DT
        theta += omega * DT
        esforco = max(-3000, min(3000, 10 * (KP * erro - KD * omega))) if controle else 0
        ref = esforco
        medida += (ref - medida) * 0.15

        sem_atitude = (t % 120) >= 113    # 7 s sem 408A2 a cada 2 min
        posicao = (theta + 180) % 360 - 180              # chega com sinal: -180 a +180
        if not sem_atitude:
            # ordem do mapa CAN novo: Esforço PID, Setpoint_atitude, "x" (antigo Azimute), Vel. angular
            frame(0x408A2, u16(esforco) + u16(setpoint) + u16(posicao) + u16(omega))
        # posição atual para o relógio: angulo do 520B6 (bytes 6-7), depois de aux1..3
        frame(0x520B6, u16(1708) + u16(8) + u16(-7) + u16(posicao))
        frame(0x1F864, u16(medida) + u16(ref) + "0000" + "0000")

        # ---- resto da telemetria (tabela do Node-RED)
        if agora >= prox_outros:
            temp = 32 + int(3 * math.sin(t / 20))
            for can_id, h in [(0x5F8B4, f"003420470A2900{temp:02X}"),
                              (0xF800, "000000000000008B"),
                              (0x3006, "0000000000000000"), (0x4F8A0, "27000A017727FB5E"),
                              (0x6F8C8, "0000000000000000")]:
                frame(can_id, h)
            prox_outros = agora + 0.4
        if agora >= prox_adsb:
            msg = ADSB[a_adsb % len(ADSB)]
            a_adsb += 1
            frame(0x600C9, msg[:14] + "00")
            frame(0x600CA, msg[14:] + "00")
            prox_adsb = agora + 1.5
        if agora >= prox_txt:
            manda("Mauasat online Compiled on Oct 29 2026 at 15:51:52")
            prox_txt = agora + 10

        time.sleep(max(0.0, DT - (time.time() - agora)))


if __name__ == "__main__":
    main()
