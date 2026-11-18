"""Comandos enviados ao CubeSat pelo módulo LoRa, uma linha cada.

As mensagens de cada botão ficam em comandos.txt (NOME = mensagem), para mudar
sem mexer no código. {SETPOINT} vira o setpoint em hex (4 dígitos, big-endian).

Atitude (CAN 2004, 8 bytes):
    byte 0     status: 80 liga a atitude, 00 desliga
    bytes 1-2  Setpoint_atitude, uint16 big-endian (0 a 359°)
    bytes 3-7  00
Ex.: liga com setpoint 16° -> {00002004:8000100000000000}\\r\\n
"""
import sys
from pathlib import Path

SETPOINT_INICIAL = 16   # 0x0010, o valor dos exemplos de liga/desliga
MARCA_SETPOINT = "{SETPOINT}"

NOMES = ("LIGA_ATITUDE", "DESLIGA_ATITUDE", "ACIONA_DEPLOYER", "DESLIGA_DEPLOYER")

# usados se o comandos.txt não existir
PADROES = {
    "LIGA_ATITUDE": "{00002004:80{SETPOINT}0000000000}",
    "DESLIGA_ATITUDE": "{00002004:00{SETPOINT}0000000000}",
    "ACIONA_DEPLOYER": "",
    "DESLIGA_DEPLOYER": "",
}


class NaoConfigurado(Exception):
    """Botão sem mensagem no comandos.txt."""


def arquivo_padrao():
    """comandos.txt ao lado do programa (no .exe: ao lado do executável)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).with_name("comandos.txt")
    return Path(__file__).with_name("comandos.txt")


def parse_commands(texto):
    """Texto do comandos.txt -> {NOME: mensagem}. ValueError em linha inválida."""
    cmds = {}
    for n, linha in enumerate(texto.splitlines(), start=1):
        linha = linha.strip()
        if not linha or linha.startswith("#"):
            continue
        nome, igual, msg = linha.partition("=")     # só o 1º "=" (Base64 tem "=")
        nome = nome.strip()
        if not igual or nome not in NOMES:
            raise ValueError(f"comandos.txt, linha {n}: esperado NOME = mensagem, "
                             f"com NOME em {', '.join(NOMES)} (lido: {linha!r})")
        cmds[nome] = msg.strip()
    return cmds


def load_commands(path=None):
    """Lê o comandos.txt; o que faltar nele vem de PADROES."""
    path = Path(path) if path else arquivo_padrao()
    cmds = dict(PADROES)
    if path.exists():
        cmds.update(parse_commands(path.read_text(encoding="utf-8-sig")))   # -sig: aceita BOM
    return cmds


def setpoint_hex(setpoint):
    if not isinstance(setpoint, int) or not 0 <= setpoint <= 359:
        raise ValueError(f"setpoint fora de 0 a 359: {setpoint}")
    return f"{setpoint:04X}"


def command_line(cmds, nome, setpoint=None):
    """Linha (bytes, com \\r\\n) do botão `nome`. NaoConfigurado se a mensagem
    estiver vazia; ValueError se ela usar {SETPOINT} e o setpoint for inválido."""
    msg = cmds.get(nome, "")
    if not msg:
        raise NaoConfigurado(f"{nome} sem mensagem no comandos.txt")
    if MARCA_SETPOINT in msg:
        msg = msg.replace(MARCA_SETPOINT, setpoint_hex(setpoint))
    return (msg + "\r\n").encode("utf-8")


def parse_setpoint(text):
    """Texto digitado -> setpoint int de 0 a 359. ValueError se não for."""
    text = text.strip()
    if not text.isdigit() or not 0 <= int(text) <= 359:
        raise ValueError(f"setpoint deve ser um inteiro de 0 a 359 (digitado: {text!r})")
    return int(text)
