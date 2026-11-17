import gc
import os
import tkinter as tk
import unittest

from dashboard import ERR, MUTED, TEXT, ClockPanel

V408 = {"Esforço PID": 0, "Setpoint_atitude": 90, "x": 45,
        "Vel. angular Azim.": 2}
V520 = {"aux1": 0, "aux2": 0, "aux3": 0, "angulo": 0}


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
        # coleta os objetos do Tk aqui, na thread principal: se o coletor rodar
        # depois dentro da thread de outro teste (ex. leitor TCP), o Tcl aborta
        # com "Tcl_AsyncDelete: async handler deleted by the wrong thread"
        del self.p, self.root
        gc.collect()

    def test_ids(self):
        self.assertEqual(self.p.can_ids(), {0x408A2, 0x520B6})

    def test_ponteiros_e_legenda(self):
        p, c = self.p, self.p.canvas
        p.push(0x408A2, 100.0, V408)
        p.push(0x520B6, 100.0, V520)
        p.redraw(100.5)
        self.root.update()
        cx, cy, _ = p._geom
        tx, ty = c.coords(p._target)[2:]          # setpoint a 90°: para a direita
        self.assertGreater(tx, cx + 10)
        self.assertAlmostEqual(ty, cy, delta=1)
        px, py = c.coords(p._current)[2:]         # angulo 0° (não o "x" = 45°): para cima
        self.assertLess(py, cy - 10)
        self.assertAlmostEqual(px, cx, delta=1)
        self.assertEqual(p._labels["setpoint"].cget("text"), "90°")
        self.assertEqual(p._labels["position"].cget("text"), "0°")
        self.assertEqual(p._labels["diff"].cget("text"), "+90°")

    def test_cores_iguais_a_legenda(self):
        p, c = self.p, self.p.canvas
        p.push(0x408A2, 100.0, V408)
        p.push(0x520B6, 100.0, V520)
        p.redraw(100.5)
        self.root.update()
        self.assertEqual(c.itemcget(p._target, "fill"), TEXT)    # setpoint: branco
        self.assertEqual(c.itemcget(p._current, "fill"), ERR)    # posição: vermelho

    def test_cada_ponteiro_fica_cinza_pela_sua_fonte(self):
        p, c = self.p, self.p.canvas
        p.push(0x408A2, 100.0, V408)
        p.push(0x520B6, 106.0, V520)
        p.redraw(106.5)
        self.root.update()
        self.assertEqual(c.itemcget(p._target, "fill"), MUTED)
        self.assertEqual(c.itemcget(p._current, "fill"), ERR)
        self.assertEqual(p._labels["stale"].cget("text"), "sem 408A2 há 6 s")

    def test_angulo_acima_de_180_aparece(self):
        p, c = self.p, self.p.canvas
        p.push(0x408A2, 100.0, V408)
        p.push(0x520B6, 100.0, dict(V520, angulo=270))
        p.redraw(100.5)
        self.root.update()
        cx, cy, _ = p._geom
        px, py = c.coords(p._current)[2:]         # 270°: para a esquerda
        self.assertEqual(c.itemcget(p._current, "state"), "normal")
        self.assertLess(px, cx - 10)
        self.assertAlmostEqual(py, cy, delta=1)
        self.assertEqual(p._labels["position"].cget("text"), "270°")

    def test_clear(self):
        p = self.p
        p.push(0x408A2, 100.0, V408)
        p.push(0x520B6, 100.0, V520)
        p.clear()
        p.redraw(100.5)
        self.root.update()
        self.assertEqual(p.canvas.itemcget(p._target, "state"), "hidden")
        self.assertEqual(p.canvas.itemcget(p._current, "state"), "hidden")
        self.assertEqual(p._labels["setpoint"].cget("text"), "—")


if __name__ == "__main__":
    unittest.main()
