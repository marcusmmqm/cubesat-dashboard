"""Lógica do relógio de atitude (sem Tk): leitura do CAN 408A2, validação dos
ângulos, diferença angular e textos da legenda.

Ângulos (Setpoint_atitude e Azimute satélite) chegam sem sinal, de 0 a 359°;
fora disso o valor é inválido. A velocidade angular chega em °/s, com sinal.
"""
import math

STALE_S = 5   # sem 408A2 por mais que isso: dado parado

F_SETPOINT = "Setpoint_atitude"
F_POSITION = "Azimute satélite"
F_VELOCITY = "Vel. angular Azim."


def valid_angle(v):
    return v is not None and 0 <= v <= 359


def angle_diff(target, current):
    """Quanto falta de `current` até `target` pelo caminho mais curto (-180 a +179)."""
    return (target - current + 180) % 360 - 180


def hand_end(cx, cy, length, deg):
    """Ponta de um ponteiro: 0° para cima, ângulos crescendo no sentido horário
    (y da tela cresce para baixo)."""
    rad = math.radians(deg)
    return cx + length * math.sin(rad), cy - length * math.cos(rad)


def _angle_text(v):
    if v is None:
        return "—"
    return f"{v}°" if valid_angle(v) else f"inválido ({v})"


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
        if valid_angle(self.position):
            self.last_valid_position = self.position

    def is_stale(self, now):
        return self.last_t is not None and now - self.last_t > STALE_S

    def legend(self, now):
        if valid_angle(self.setpoint) and valid_angle(self.position):
            diff = f"{angle_diff(self.setpoint, self.position):+d}°"
        else:
            diff = "—"
        return {
            "setpoint": _angle_text(self.setpoint),
            "position": _angle_text(self.position),
            "velocity": "—" if self.velocity is None else f"{self.velocity:+d} °/s",
            "diff": diff,
            "stale": f"sem dados há {int(now - self.last_t)} s" if self.is_stale(now) else None,
        }
