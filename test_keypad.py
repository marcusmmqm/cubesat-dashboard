import gc
import os
import tkinter as tk
import unittest

from dashboard import FitLabel, Keypad


@unittest.skipUnless(os.environ.get("DISPLAY"), "precisa de display")
class KeypadTest(unittest.TestCase):
    """Teclado numérico na tela de toque (o teclado virtual do Raspberry não
    aparece para o Tk)."""

    def setUp(self):
        self.root = tk.Tk()
        self.root.geometry("800x436")
        self.escolhidos = []
        self.k = Keypad(self.root, self.escolhidos.append)
        self.root.update()

    def tearDown(self):
        self.root.destroy()
        del self.k, self.root
        gc.collect()

    def teclar(self, *teclas):
        for t in teclas:
            self.k.press(t)

    def test_abre_com_o_valor_atual(self):
        self.assertFalse(self.k.is_open)
        self.k.open("16")
        self.assertTrue(self.k.is_open)
        self.assertEqual(self.k.text, "16")

    def test_digita_e_confirma(self):
        self.k.open("16")
        self.teclar("⌫", "⌫", "3", "0", "0", "OK")
        self.assertEqual(self.escolhidos, [300])
        self.assertFalse(self.k.is_open)

    def test_no_maximo_3_digitos(self):
        self.k.open("")
        self.teclar("1", "2", "3", "4")
        self.assertEqual(self.k.text, "123")

    def test_fora_da_faixa_nao_confirma(self):
        self.k.open("")
        self.teclar("4", "0", "0", "OK")
        self.assertEqual(self.escolhidos, [])
        self.assertTrue(self.k.is_open)          # continua aberto para corrigir
        self.teclar("⌫", "⌫", "⌫", "OK")         # vazio também não confirma
        self.assertEqual(self.escolhidos, [])

    def test_cancelar(self):
        self.k.open("90")
        self.teclar("5", "Cancelar")
        self.assertEqual(self.escolhidos, [])
        self.assertFalse(self.k.is_open)


@unittest.skipUnless(os.environ.get("DISPLAY"), "precisa de display")
class FitLabelTest(unittest.TestCase):
    """Texto da barra do topo: encurta com "…" para caber, sem cobrir botões."""

    def setUp(self):
        self.root = tk.Tk()
        self.l = FitLabel(self.root, font=("DejaVu Sans", 9))
        self.l.place(x=0, y=0, width=120, height=20)
        self.root.update()

    def tearDown(self):
        self.root.destroy()
        del self.l, self.root
        gc.collect()

    def test_texto_curto_fica_inteiro(self):
        self.l.set("● ok · 12", "#fff")
        self.assertEqual(self.l.cget("text"), "● ok · 12")

    def test_texto_longo_encurta_e_cabe(self):
        longo = "Aciona deployer: NÃO enviado (não configurado no comandos.txt)"
        self.l.set(longo, "#f00")
        t = self.l.cget("text")
        self.assertTrue(t.endswith("…") and longo.startswith(t[:-1]), t)
        self.assertLessEqual(self.l.medir(t), 120)
        self.assertEqual(self.l.cget("fg"), "#f00")

    def test_volta_a_crescer_quando_ha_espaco(self):
        longo = "Aciona deployer: NÃO enviado (não configurado no comandos.txt)"
        self.l.set(longo, "#f00")
        self.l.place(width=600)
        self.root.update()
        self.assertEqual(self.l.cget("text"), longo)


if __name__ == "__main__":
    unittest.main()
