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


def _u8(data, n):
    data = data.ljust(n, b"\x00")
    return list(data[:n])


# id -> (lista de nomes dos campos, função de decodificação)
DECODERS = {
    0x1F864: (
        ["MeasuredSpeed", "RefSpeed", "Measured Current", "RefTorque"],
        # little-endian com sinal: roda parada dá ±122 (em big-endian daria
        # 31232 / -30977, que era o que o Node-RED mostrava).
        lambda d: _s16_le(d, 4),
    ),
    0x408A2: (
        ["RefSpeed Roda Reação", "Esforço PID",   # nomes de mapaCAN2.png
         "Azimute satélite", "Vel. angular Azim."],
        lambda d: _u16_be(d, 4),
    ),
    0x520B6: (
        ["v_solar_bottom", "v_solar_Yminus", "v_solar_Y", "v_solar_Xminus",
         "v_solar_X", "v_solar_top", "v_solar_vout", "STATUS"],
        lambda d: _u8(d, 8),
    ),
}


def decode(can_id, data):
    """Retorna {nome_do_campo: valor} para IDs conhecidos, ou None."""
    entry = DECODERS.get(can_id)
    if entry is None:
        return None
    names, fn = entry
    return dict(zip(names, fn(data)))
