"""Decodifica as mensagens CAN que chegam pelo receptor LoRa (serial).

Formatos aceitos (uma mensagem por linha):
    {0001F864:7A00000000000000}
    {0001F864 7A 00 00 00 00 00 00 00}
"""
import re

_MSG_RE = re.compile(
    # exatamente 8 bytes de dados: linha cortada é descartada, não completada com 0
    r"\{\s*([0-9A-Fa-f]{1,8})[:\s]\s*((?:[0-9A-Fa-f]{2}\s*){8})\}"
)


def parse_line(line):
    """Retorna (can_id:int, data:bytes) ou None se a linha não for uma mensagem."""
    if isinstance(line, (bytes, bytearray)):
        line = line.decode("ascii", errors="ignore")
    m = _MSG_RE.search(line)
    if not m:
        return None
    can_id = int(m.group(1), 16)
    data = bytes.fromhex(re.sub(r"\s+", "", m.group(2)))
    return can_id, data


def _u16_be(data, n):
    """n campos uint16 big-endian (mesma regra do codec do Node-RED)."""
    data = data.ljust(2 * n, b"\x00")
    return [data[2 * i] << 8 | data[2 * i + 1] for i in range(n)]


def to_int16(v):
    """Reinterpreta um uint16 como int16 com sinal (complemento de 2)."""
    return v - 0x10000 if v >= 0x8000 else v


def _s16_le(data, n):
    """n campos int16 little-endian com sinal."""
    data = data.ljust(2 * n, b"\x00")
    return [int.from_bytes(data[2 * i:2 * i + 2], "little", signed=True)
            for i in range(n)]


def _s16_be(data, n):
    """n campos int16 big-endian com sinal."""
    data = data.ljust(2 * n, b"\x00")
    return [int.from_bytes(data[2 * i:2 * i + 2], "big", signed=True)
            for i in range(n)]


def _u8(data, n):
    data = data.ljust(n, b"\x00")
    return list(data[:n])


# id -> (lista de nomes dos campos, função de decodificação)
DECODERS = {
    0x1F864: (
        ["MeasuredSpeed", "RefSpeed", "Measured Current", "RefTorque"],
        # int16 big-endian com sinal
        lambda d: _s16_be(d, 4),
    ),
    0x408A2: (
        # ordem de NovoMapaCANParaAjusteCodigo.png (canId_13 no Node-RED)
        ["Esforço PID", "Setpoint_atitude", "x", "Vel. angular Azim."],
        # big-endian; Setpoint_atitude (campo 1) sem sinal (0 a 359°); Esforço PID,
        # "x" e velocidade angular (°/s) com sinal.
        # "x" (bytes 4-5) era o "Azimute satélite": não é mais usado (a posição
        # atual do relógio vem do angulo do 520B6); o significado fica para depois
        lambda d: [v if i == 1 else to_int16(v) for i, v in enumerate(_u16_be(d, 4))],
    ),
    0x520B6: (
        # 4 × int16 big-endian com sinal: aux1 (bytes 0-1, antes v_solar_bottom e
        # v_solar_Yminus), aux2 (2-3, v_solar_Y e v_solar_Xminus), aux3 (4-5,
        # v_solar_X e v_solar_top) e angulo (6-7, posição atual, -180 a +180°)
        ["aux1", "aux2", "aux3", "angulo"],
        lambda d: _s16_be(d, 4),
    ),
}


def decode(can_id, data):
    """Retorna {nome_do_campo: valor} para IDs conhecidos, ou None."""
    entry = DECODERS.get(can_id)
    if entry is None:
        return None
    names, fn = entry
    return dict(zip(names, fn(data)))
