import unittest

from attitude import Attitude, angle_diff, hand_end, position_deg, valid_angle


class AngleTest(unittest.TestCase):
    def test_valid(self):
        self.assertTrue(valid_angle(0))
        self.assertTrue(valid_angle(359))
        self.assertFalse(valid_angle(360))
        self.assertFalse(valid_angle(65485))

    def test_posicao_qualquer_valor_vira_0_a_359(self):   # nunca inválida
        self.assertEqual(position_deg(-51), 309)
        self.assertEqual(position_deg(-180), 180)
        self.assertEqual(position_deg(180), 180)
        self.assertEqual(position_deg(181), 181)        # passou de 180: continua valendo
        self.assertEqual(position_deg(200), 200)
        self.assertEqual(position_deg(359), 359)
        self.assertEqual(position_deg(360), 0)
        self.assertEqual(position_deg(370), 10)
        self.assertEqual(position_deg(0), 0)
        self.assertIsNone(position_deg(None))

    def test_diff(self):
        self.assertEqual(angle_diff(350, 10), -20)   # caminho curto, não +340
        self.assertEqual(angle_diff(10, 350), 20)
        self.assertEqual(angle_diff(15, 309), 66)
        self.assertEqual(angle_diff(100, 100), 0)

    def test_hand_end(self):
        for deg, (x, y) in [(0, (0, -10)), (90, (10, 0)), (180, (0, 10)), (270, (-10, 0))]:
            ex, ey = hand_end(0, 0, 10, deg)
            self.assertAlmostEqual(ex, x)
            self.assertAlmostEqual(ey, y)


class AttitudeTest(unittest.TestCase):
    # setpoint e velocidade vêm do 408A2; a posição atual, do angulo do 520B6
    # (com sinal, -180 a +180: -51 = 309°)
    V408 = {"Esforço PID": 0, "Setpoint_atitude": 15, "x": 90,
            "Vel. angular Azim.": 2}
    V520 = {"aux1": 0, "aux2": 0, "aux3": 0, "angulo": -51}

    def cheio(self, t=100.0):
        a = Attitude()
        a.update(0x408A2, t, self.V408)
        a.update(0x520B6, t, self.V520)
        return a

    def test_sem_dados(self):
        a = Attitude()
        self.assertEqual(a.legend(100.0), {"setpoint": "—", "position": "—",
                                           "velocity": "—", "diff": "—", "stale": None})

    def test_valores(self):
        self.assertEqual(self.cheio().legend(101.0),
                         {"setpoint": "15°", "position": "309°", "velocity": "+2 °/s",
                          "diff": "+66°", "stale": None})

    def test_posicao_vem_do_angulo_do_520b6(self):
        a = Attitude()
        a.update(0x408A2, 100.0, self.V408)             # campo "x" (antigo Azimute) = 90: ignorado
        self.assertEqual(a.legend(100.0)["position"], "—")
        a.update(0x520B6, 100.0, self.V520)
        self.assertEqual(a.legend(100.0)["position"], "309°")
        self.assertEqual(a.last_valid_position, 309)

    def test_outros_ids_ignorados(self):
        a = Attitude()
        a.update(0x1F864, 100.0, {"MeasuredSpeed": 5})
        self.assertEqual(a.legend(100.0)["setpoint"], "—")

    def test_posicao_acima_de_180(self):
        a = self.cheio()
        a.update(0x520B6, 101.0, dict(self.V520, angulo=200))
        leg = a.legend(101.0)
        self.assertEqual(leg["position"], "200°")
        self.assertEqual(leg["diff"], "+175°")          # de 200° até 15°: +175
        self.assertEqual(a.last_valid_position, 200)

    def test_velocidade_negativa(self):
        a = Attitude()
        a.update(0x408A2, 100.0, dict(self.V408, **{"Vel. angular Azim.": -3}))
        self.assertEqual(a.legend(100.0)["velocity"], "-3 °/s")

    def test_parado_por_fonte(self):
        a = Attitude()
        a.update(0x408A2, 100.0, self.V408)
        a.update(0x520B6, 103.0, self.V520)
        self.assertFalse(a.target_stale(105.0))
        self.assertTrue(a.target_stale(106.0))
        self.assertFalse(a.position_stale(106.0))
        self.assertEqual(a.legend(106.2)["stale"], "sem 408A2 há 6 s")
        self.assertEqual(a.legend(109.5)["stale"], "sem 408A2 há 9 s · sem 520B6 há 6 s")

    def test_clear(self):
        a = self.cheio()
        a.clear()
        self.assertIsNone(a.last_valid_setpoint)
        self.assertIsNone(a.last_valid_position)
        self.assertEqual(a.legend(100.0)["setpoint"], "—")
        self.assertIsNone(a.legend(200.0)["stale"])


if __name__ == "__main__":
    unittest.main()
