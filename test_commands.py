import queue
import time
import unittest
from pathlib import Path

from commands import (NOMES, SETPOINT_INICIAL, NaoConfigurado, command_line,
                      load_commands, parse_commands, parse_setpoint)
from dashboard import SerialReader

EXEMPLO = """
# comentário
LIGA_ATITUDE     = {00002004:80{SETPOINT}0000000000}
DESLIGA_ATITUDE  = {00002004:00{SETPOINT}0000000000}
ACIONA_DEPLOYER  = {"devEui": "0005168000136ee4","data": "AAE="}
DESLIGA_DEPLOYER =
"""


class ArquivoDeComandosTest(unittest.TestCase):
    def test_le_nome_e_mensagem(self):
        c = parse_commands(EXEMPLO)
        self.assertEqual(c["LIGA_ATITUDE"], "{00002004:80{SETPOINT}0000000000}")
        # só o primeiro "=" separa: o "=" do Base64 fica na mensagem
        self.assertEqual(c["ACIONA_DEPLOYER"], '{"devEui": "0005168000136ee4","data": "AAE="}')
        self.assertEqual(c["DESLIGA_DEPLOYER"], "")

    def test_nome_desconhecido_e_erro(self):
        # erro de digitação no nome não pode passar em silêncio
        with self.assertRaises(ValueError):
            parse_commands("LIGA_ATITUD = {00002004:8000100000000000}")
        with self.assertRaises(ValueError):
            parse_commands("linha sem igual")

    def test_arquivo_da_pasta(self):
        # comandos.txt como vai no repositório: os exemplos de liga/desliga com 16°
        c = load_commands()
        self.assertEqual(set(c), set(NOMES))
        self.assertEqual(command_line(c, "LIGA_ATITUDE", 16), b"{00002004:8000100000000000}\r\n")
        self.assertEqual(command_line(c, "DESLIGA_ATITUDE", 16), b"{00002004:0000100000000000}\r\n")

    def test_arquivo_salvo_com_bom_do_bloco_de_notas(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "comandos.txt"
            p.write_bytes("﻿# comentário\nACIONA_DEPLOYER = {00003008:01}\n".encode("utf-8"))
            self.assertEqual(load_commands(p)["ACIONA_DEPLOYER"], "{00003008:01}")

    def test_arquivo_ausente_usa_os_padroes(self):
        c = load_commands(Path("/nao/existe/comandos.txt"))
        self.assertEqual(command_line(c, "LIGA_ATITUDE", 300), b"{00002004:80012C0000000000}\r\n")
        with self.assertRaises(NaoConfigurado):
            command_line(c, "ACIONA_DEPLOYER")


class LinhaDeComandoTest(unittest.TestCase):
    def setUp(self):
        self.c = parse_commands(EXEMPLO)

    def test_setpoint_em_hex_big_endian(self):
        self.assertEqual(SETPOINT_INICIAL, 16)
        self.assertEqual(command_line(self.c, "LIGA_ATITUDE", 300), b"{00002004:80012C0000000000}\r\n")
        self.assertEqual(command_line(self.c, "LIGA_ATITUDE", 0), b"{00002004:8000000000000000}\r\n")
        self.assertEqual(command_line(self.c, "DESLIGA_ATITUDE", 359), b"{00002004:0001670000000000}\r\n")

    def test_setpoint_fora_da_faixa(self):
        for v in (-1, 360, None):
            with self.assertRaises(ValueError):
                command_line(self.c, "LIGA_ATITUDE", v)

    def test_mensagem_sem_setpoint(self):
        self.assertEqual(command_line(self.c, "ACIONA_DEPLOYER"),
                         b'{"devEui": "0005168000136ee4","data": "AAE="}\r\n')

    def test_mensagem_vazia_nao_configurada(self):
        with self.assertRaises(NaoConfigurado):
            command_line(self.c, "DESLIGA_DEPLOYER")

    def test_parse_setpoint(self):
        self.assertEqual(parse_setpoint(" 300 "), 300)
        self.assertEqual(parse_setpoint("0"), 0)
        for texto in ("", "abc", "12.5", "360", "-5"):
            with self.assertRaises(ValueError):
                parse_setpoint(texto)


class SerialSendTest(unittest.TestCase):
    def test_sem_conexao_nao_envia(self):
        r = SerialReader("loop://", 115200, queue.Queue())   # thread não iniciada
        self.assertFalse(r.send(b"{00002004:8000100000000000}\r\n"))

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
            self.assertTrue(r.send(b"{00002004:0000100000000000}\r\n"))
            _, can_id, data = q.get(timeout=3)
        finally:
            r.stop()
            r.join(timeout=3)
        self.assertEqual((can_id, data), (0x2004, bytes.fromhex("0000100000000000")))


if __name__ == "__main__":
    unittest.main()
