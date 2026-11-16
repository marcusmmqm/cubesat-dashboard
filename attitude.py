"""Lógica do relógio de atitude (sem Tk): leitura do CAN 408A2, validação dos
ângulos, diferença angular e textos da legenda.

O Setpoint_atitude chega sem sinal, de 0 a 359°. A posição atual (Azimute
satélite) chega com sinal, de -180 a +180°, e é mostrada de 0 a 359° (-51 -> 309).
Fora dessas faixas o valor é inválido. A velocidade angular chega em °/s, com sinal.
"""
import math

STALE_S = 5   # sem 408A2 por mais que isso: dado parado

F_SETPOINT = "Setpoint_atitude"
F_POSITION = "Azimute satélite"
F_VELOCITY = "Vel. angular Azim."


def valid_angle(v):
    return v is not None and 0 <= v <= 359


def position_deg(v):
    """Posição atual (-180 a +180°, com sinal) em 0 a 359°; None se fora da faixa."""
    if v is None or not -180 <= v <= 180:
        return None
    return v % 360


def angle_diff(target, current):
    """Quanto falta de `current` até `target` pelo caminho mais curto (-180 a +179)."""
    return (target - current + 180) % 360 - 180


def hand_end(cx, cy, length, deg):
    """Ponta de um ponteiro: 0° para cima, ângulos crescendo no sentido horário
    (y da tela cresce para baixo)."""
    rad = math.radians(deg)
    return cx + length * math.sin(rad), cy - length * math.cos(rad)


def _angle_text(raw, deg):
    """raw = valor recebido; deg = o mesmo em 0 a 359° (None se inválido)."""
    if raw is None:
        return "—"
    return f"{deg}°" if deg is not None else f"inválido ({raw})"


class Attitude:
    """Últimos valores recebidos do 408A2."""

    def __init__(self):
        self.clear()

    def clear(self):
        self.setpoint = self.position = self.velocity = None   # últimos valores crus
        self.last_valid_setpoint = self.last_valid_position = None
        self.last_t = None

    def update(self, t, values):
        self.last_t = t
        self.setpoint = values[F_SETPOINT]
        self.position = values[F_POSITION]
        self.velocity = values[F_VELOCITY]
        if valid_angle(self.setpoint):
            self.last_valid_setpoint = self.setpoint
        if position_deg(self.position) is not None:
            self.last_valid_position = position_deg(self.position)

    def is_stale(self, now):
        return self.last_t is not None and now - self.last_t > STALE_S

    def legend(self, now):
        setpoint = self.setpoint if valid_angle(self.setpoint) else None
        position = position_deg(self.position)
        if setpoint is not None and position is not None:
            diff = f"{angle_diff(setpoint, position):+d}°"
        else:
            diff = "—"
        return {
            "setpoint": _angle_text(self.setpoint, setpoint),
            "position": _angle_text(self.position, position),
            "velocity": "—" if self.velocity is None else f"{self.velocity:+d} °/s",
            "diff": diff,
            "stale": f"sem dados há {int(now - self.last_t)} s" if self.is_stale(now) else None,
        }
