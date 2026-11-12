import unittest
from types import SimpleNamespace as P

from dashboard import choose_port


class ChoosePortTest(unittest.TestCase):
    def test_prefere_ftdi(self):
        ports = [P(device="COM1", vid=None), P(device="COM4", vid=0x10C4),
                 P(device="COM7", vid=0x0403)]
        self.assertEqual(choose_port(ports), "COM7")

    def test_sem_ftdi_usa_porta_usb(self):
        ports = [P(device="COM1", vid=None), P(device="COM4", vid=0x10C4)]
        self.assertEqual(choose_port(ports), "COM4")

    def test_ignora_portas_internas(self):
        self.assertIsNone(choose_port([P(device="/dev/ttyS0", vid=None),
                                       P(device="COM1", vid=None)]))

    def test_nenhuma_porta(self):
        self.assertIsNone(choose_port([]))


if __name__ == "__main__":
    unittest.main()
