import unittest

from can_parser import decode, parse_line, to_int16


class ParseLineTest(unittest.TestCase):
    def test_formato_com_dois_pontos(self):
        self.assertEqual(
            parse_line(b"{0001F864:7A00000000000000}\r\n"),
            (0x1F864, bytes.fromhex("7A00000000000000")),
        )

    def test_formato_com_espacos(self):
        self.assertEqual(
            parse_line("{000520B6 17 0A 05 03 01 01 00 00}"),
            (0x520B6, bytes.fromhex("170A050301010000")),
        )

    def test_lixo_antes_da_mensagem(self):
        self.assertEqual(
            parse_line(b"\x00{000408A2:0000000000910000}"),
            (0x408A2, bytes.fromhex("0000000000910000")),
        )

    def test_linha_truncada_e_rejeitada(self):
        # Sem isso, "86FF" viraria 86FF000000000000 e os campos faltantes = 0.
        self.assertIsNone(parse_line(b"{0001F864:86FF}"))
        self.assertIsNone(parse_line(b"{000520B6 17 0A 05}"))
        self.assertIsNone(parse_line(b"{0001F864:86FF0000000000000000}"))  # 9 bytes

    def test_linha_invalida(self):
        self.assertIsNone(parse_line(b"Cubesat MAUASAT online 433Mhz"))
        self.assertIsNone(parse_line(b"{0004"))


class DecodeTest(unittest.TestCase):
    def test_1f864_int16_little_endian(self):
        # Roda parada: ontem chegava 7A00..., hoje 86FF... -> +122 / -122.
        # Em big-endian isso daria 31232 / -30977 (o que o Node-RED mostrava).
        self.assertEqual(decode(0x1F864, bytes.fromhex("7A00000000000000"))["MeasuredSpeed"], 122)
        self.assertEqual(decode(0x1F864, bytes.fromhex("86FF000000000000"))["MeasuredSpeed"], -122)
        v = decode(0x1F864, bytes.fromhex("0100020003000000"))
        self.assertEqual(v["RefSpeed"], 2)
        self.assertEqual(v["Measured Current"], 3)
        self.assertEqual(v["RefTorque"], 0)

    def test_408a2(self):
        v = decode(0x408A2, bytes.fromhex("00010002FF910004"))
        self.assertEqual(v["RefSpeed Roda Reação"], 1)
        self.assertEqual(v["Esforço PID"], 2)  # mapaCAN2.png
        self.assertEqual(v["Azimute satélite"], 65425)  # valor da imagem
        self.assertEqual(v["Vel. angular Azim."], 4)

    def test_520b6_um_byte_por_campo(self):
        v = decode(0x520B6, bytes.fromhex("170A050301010000"))
        self.assertEqual(
            list(v.values()), [23, 10, 5, 3, 1, 1, 0, 0]  # valores da imagem
        )

    def test_to_int16(self):
        self.assertEqual(to_int16(0x0000), 0)
        self.assertEqual(to_int16(0x07D0), 2000)
        self.assertEqual(to_int16(0xFF86), -122)
        self.assertEqual(to_int16(0x8000), -32768)
        self.assertEqual(to_int16(-122), -122)   # já com sinal: não mexe

    def test_id_desconhecido(self):
        self.assertIsNone(decode(0x4F8A0, bytes(8)))


if __name__ == "__main__":
    unittest.main()
