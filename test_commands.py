import queue
import time
import unittest

from commands import SETPOINT_INICIAL, attitude_command, parse_setpoint
from dashboard import SerialReader


class ComandosTest(unittest.TestCase):
    def test_linhas_dos_exemplos(self):
        # setpoint 16 = 0x0010 nos bytes 1-2
        self.assertEqual(SETPOINT_INICIAL, 16)
        self.assertEqual(attitude_command(True, 16), b"{00002004:8000100000000000}\r\n")
        self.assertEqual(attitude_command(False, 16), b"{00002004:0000100000000000}\r\n")

    def test_setpoint_big_endian_nos_bytes_1_e_2(self):
        self.assertEqual(attitude_command(True, 300), b"{00002004:80012C0000000000}\r\n")
        self.assertEqual(attitude_command(True, 0), b"{00002004:8000000000000000}\r\n")
        self.assertEqual(attitude_command(False, 359), b"{00002004:0001670000000000}\r\n")

    def test_setpoint_fora_da_faixa(self):
        for v in (-1, 360, 1000):
            with self.assertRaises(ValueError):
                attitude_command(True, v)

    def test_parse_setpoint(self):
        self.assertEqual(parse_setpoint(" 300 "), 300)
        self.assertEqual(parse_setpoint("0"), 0)
        for texto in ("", "abc", "12.5", "360", "-5"):
            with self.assertRaises(ValueError):
                parse_setpoint(texto)


class SerialSendTest(unittest.TestCase):
    def test_sem_conexao_nao_envia(self):
        r = SerialReader("loop://", 115200, queue.Queue())   # thread não iniciada
        self.assertFalse(r.send(attitude_command(True, 16)))

    def test_envia_pela_mesma_porta_que_le(self):
        # loop:// devolve o que foi escrito: o comando enviado volta como leitura
        q = queue.Queue()
        r = SerialReader("loop://", 115200, q)
        r.start()
        try:
            for _ in range(100):
                if r.connected:
                    break
                time.sleep(0.02)
            self.assertTrue(r.send(attitude_command(False, 16)))
            _, can_id, data = q.get(timeout=3)
        finally:
            r.stop()
            r.join(timeout=3)
        self.assertEqual((can_id, data), (0x2004, bytes.fromhex("0000100000000000")))


if __name__ == "__main__":
    unittest.main()
