"""Lógica do relógio de atitude (sem Tk): leitura dos CAN 408A2 e 520B6, validação
dos ângulos, diferença angular e textos da legenda.

Do 408A2 vêm o Setpoint_atitude (sem sinal, 0 a 359°) e a velocidade angular
(°/s, com sinal). A posição atual vem do angulo do 520B6: com sinal, de -180 a
+180°, mostrada de 0 a 359° (-51 -> 309). Fora dessas faixas o valor é inválido.
"""
import math

STALE_S = 5   # sem mensagem do ID por mais que isso: dado parado

CAN_TARGET = 0x408A2      # setpoint e velocidade angular
CAN_POSITION = 0x520B6    # posição atual (angulo)

F_SETPOINT = "Setpoint_atitude"
F_VELOCITY = "Vel. angular Azim."
F_POSITION = "angulo"


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


def _stale(last_t, now):
    return last_t is not None and now - last_t > STALE_S


class Attitude:
    """Últimos valores recebidos do 408A2 (alvo) e do 520B6 (posição)."""

    def __init__(self):
        self.clear()

    def clear(self):
        self.setpoint = self.position = self.velocity = None   # últimos valores crus
        self.last_valid_setpoint = self.last_valid_position = None
        self.t_target = self.t_position = None                # hora da última mensagem

    def update(self, can_id, t, values):
        if can_id == CAN_TARGET:
            self.t_target = t
            self.setpoint = values[F_SETPOINT]
            self.velocity = values[F_VELOCITY]
            if valid_angle(self.setpoint):
                self.last_valid_setpoint = self.setpoint
        elif can_id == CAN_POSITION:
            self.t_position = t
            self.position = values[F_POSITION]
            if position_deg(self.position) is not None:
                self.last_valid_position = position_deg(self.position)

    def target_stale(self, now):
        return _stale(self.t_target, now)

    def position_stale(self, now):
        return _stale(self.t_position, now)

    def legend(self, now):
        setpoint = self.setpoint if valid_angle(self.setpoint) else None
        position = position_deg(self.position)
        if setpoint is not None and position is not None:
            diff = f"{angle_diff(setpoint, position):+d}°"
        else:
            diff = "—"
        parados = [f"sem {nome} há {int(now - t)} s"
                   for nome, t in (("408A2", self.t_target), ("520B6", self.t_position))
                   if _stale(t, now)]
        return {
            "setpoint": _angle_text(self.setpoint, setpoint),
            "position": _angle_text(self.position, position),
            "velocity": "—" if self.velocity is None else f"{self.velocity:+d} °/s",
            "diff": diff,
            "stale": " · ".join(parados) or None,
        }
