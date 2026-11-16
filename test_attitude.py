import unittest

from attitude import Attitude, angle_diff, hand_end, valid_angle


class AngleTest(unittest.TestCase):
    def test_valid(self):
        self.assertTrue(valid_angle(0))
        self.assertTrue(valid_angle(359))
        self.assertFalse(valid_angle(360))
        self.assertFalse(valid_angle(65485))

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
    V = {"Setpoint_atitude": 15, "Esforço PID": 0, "Azimute satélite": 309,
         "Vel. angular Azim.": 2}

    def test_sem_dados(self):
        a = Attitude()
        self.assertEqual(a.legend(100.0), {"setpoint": "—", "position": "—",
                                           "velocity": "—", "diff": "—", "stale": None})

    def test_valores(self):
        a = Attitude()
        a.update(100.0, self.V)
        self.assertEqual(a.legend(101.0), {"setpoint": "15°", "position": "309°",
                                           "velocity": "+2 °/s", "diff": "+66°",
                                           "stale": None})

    def test_invalido_mantem_ultimo_valido(self):
        a = Attitude()
        a.update(100.0, self.V)
        a.update(101.0, dict(self.V, **{"Azimute satélite": 65485}))
        leg = a.legend(101.0)
        self.assertEqual(leg["position"], "inválido (65485)")
        self.assertEqual(leg["diff"], "—")
        self.assertEqual(a.last_valid_position, 309)

    def test_velocidade_negativa(self):
        a = Attitude()
        a.update(100.0, dict(self.V, **{"Vel. angular Azim.": -3}))
        self.assertEqual(a.legend(100.0)["velocity"], "-3 °/s")

    def test_parado(self):
        a = Attitude()
        a.update(100.0, self.V)
        self.assertFalse(a.is_stale(105.0))
        self.assertTrue(a.is_stale(106.0))
        self.assertEqual(a.legend(106.2)["stale"], "sem dados há 6 s")

    def test_clear(self):
        a = Attitude()
        a.update(100.0, self.V)
        a.clear()
        self.assertIsNone(a.last_valid_setpoint)
        self.assertEqual(a.legend(100.0)["setpoint"], "—")


if __name__ == "__main__":
    unittest.main()
