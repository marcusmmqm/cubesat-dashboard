"""Comandos enviados ao CubeSat pela serial do LoRa (FTDI), uma linha cada.

ID 2004 (8 bytes):
    byte 0     status: 80 liga a atitude, 00 desliga
    bytes 1-2  Setpoint_atitude, uint16 big-endian (0 a 359°)
    bytes 3-7  00

Ex.: liga com setpoint 16° -> {00002004:8000100000000000}\\r\\n
"""

CAN_ATITUDE = 0x2004
SETPOINT_INICIAL = 16   # 0x0010, o valor dos exemplos de liga/desliga


def attitude_command(on, setpoint):
    """Linha (bytes) do comando de atitude: liga (on=True) ou desliga, com o setpoint."""
    if not 0 <= setpoint <= 359:
        raise ValueError(f"setpoint fora de 0 a 359: {setpoint}")
    data = bytes([0x80 if on else 0x00]) + setpoint.to_bytes(2, "big") + bytes(5)
    return f"{{{CAN_ATITUDE:08X}:{data.hex().upper()}}}\r\n".encode("ascii")


def parse_setpoint(text):
    """Texto digitado -> setpoint int de 0 a 359. ValueError se não for."""
    text = text.strip()
    if not text.isdigit() or not 0 <= int(text) <= 359:
        raise ValueError(f"setpoint deve ser um inteiro de 0 a 359 (digitado: {text!r})")
    return int(text)
