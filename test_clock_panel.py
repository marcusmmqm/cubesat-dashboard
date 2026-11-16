import os
import tkinter as tk
import unittest

from dashboard import MUTED, ClockPanel

V = {"Setpoint_atitude": 90, "Esforço PID": 0, "Azimute satélite": 0, "Vel. angular Azim.": 2}


@unittest.skipUnless(os.environ.get("DISPLAY"), "precisa de display")
class ClockPanelTest(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.geometry("400x400")
        self.p = ClockPanel(self.root)
        self.p.pack(fill="both", expand=True)
        self.root.update()

    def tearDown(self):
        self.root.destroy()

    def test_ponteiros_e_legenda(self):
        p, c = self.p, self.p.canvas
        p.push(0x408A2, 100.0, V)
        p.redraw(100.5)
        self.root.update()
        cx, cy, _ = p._geom
        tx, ty = c.coords(p._target)[2:]          # vermelho a 90°: para a direita
        self.assertGreater(tx, cx + 10)
        self.assertAlmostEqual(ty, cy, delta=1)
        px, py = c.coords(p._current)[2:]         # branco a 0°: para cima
        self.assertLess(py, cy - 10)
        self.assertAlmostEqual(px, cx, delta=1)
        self.assertEqual(p._labels["setpoint"].cget("text"), "90°")
        self.assertEqual(p._labels["diff"].cget("text"), "+90°")

    def test_parado_fica_cinza(self):
        p, c = self.p, self.p.canvas
        p.push(0x408A2, 100.0, V)
        p.redraw(106.5)
        self.root.update()
        self.assertEqual(c.itemcget(p._target, "fill"), MUTED)
        self.assertEqual(p._labels["stale"].cget("text"), "sem dados há 6 s")

    def test_sem_angulo_valido_ponteiro_oculto(self):
        p, c = self.p, self.p.canvas
        p.push(0x408A2, 100.0, dict(V, **{"Azimute satélite": 65485}))
        p.redraw(100.5)
        self.root.update()
        self.assertEqual(c.itemcget(p._current, "state"), "hidden")
        self.assertEqual(c.itemcget(p._target, "state"), "normal")

    def test_clear(self):
        p = self.p
        p.push(0x408A2, 100.0, V)
        p.clear()
        p.redraw(100.5)
        self.root.update()
        self.assertEqual(p.canvas.itemcget(p._target, "state"), "hidden")
        self.assertEqual(p._labels["setpoint"].cget("text"), "—")


if __name__ == "__main__":
    unittest.main()
