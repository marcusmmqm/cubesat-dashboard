"""Funções JavaScript do fluxo do Raspberry (node-red/gerar_fluxo_rasp.py),
rodadas no Node.js com um node/global de mentira. As mensagens vêm do
comandos.txt (aqui, um de exemplo)."""
import base64
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "node-red"))
import gerar_fluxo_rasp as g  # noqa: E402
from commands import parse_commands  # noqa: E402

HARNESS = r"""
const {code, msg, globals} = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const status = [];
const node = {status: s => status.push(s), warn: () => {}, error: () => {}};
const global = {get: k => globals[k], set: (k, v) => { globals[k] = v; }};
const out = new Function('msg', 'node', 'global', 'Buffer', code)(msg, node, global, Buffer);
console.log(JSON.stringify({out: out === undefined ? null : out, status}));
"""

CMDS = parse_commands("""
LIGA_ATITUDE     = {00002004:80{SETPOINT}0000000000}
DESLIGA_ATITUDE  = {00002004:00{SETPOINT}0000000000}
ACIONA_DEPLOYER  = {00003008:0100000000000000}
DESLIGA_DEPLOYER =
""")


def rodar(code, msg, globais=None):
    r = subprocess.run(["node", "-e", HARNESS], input=json.dumps(
        {"code": code, "msg": msg, "globals": globais or {}}),
        capture_output=True, text=True, check=True)
    return json.loads(r.stdout)["out"]


def chirpstack(*bytes_):
    data = base64.b64encode(bytes(bytes_)).decode()
    return {"payload": '{"devEui": "0005168000136ee4","confirmed": true,'
                       f'"fPort": 1,"data": "{data}"}}'}


@unittest.skipUnless(shutil.which("node"), "precisa do Node.js")
class EnviarPeloLoraTest(unittest.TestCase):
    """Botões do painel Node-RED (depois de Update + PIN) -> serial."""

    def enviar(self, msg, globais=None):
        return rodar(g.func_enviar(CMDS), msg, globais)

    def test_liga_atitude_com_o_setpoint(self):
        serial, ultimo = self.enviar(chirpstack(0, 5, 0x01, 0x2C))
        self.assertEqual(serial["payload"], "{00002004:80012C0000000000}\r\n")
        self.assertIn("LIGA ATITUDE 300°", ultimo["payload"])

    def test_desliga_atitude_leva_o_ultimo_setpoint(self):
        serial, _ = self.enviar(chirpstack(0, 4), {"GlobalCubesat.azimute_set": "90"})
        self.assertEqual(serial["payload"], "{00002004:00005A0000000000}\r\n")

    def test_desliga_sem_setpoint_usa_16(self):
        for globais in ({}, {"GlobalCubesat.azimute_set": ""}):
            serial, _ = self.enviar(chirpstack(0, 4), globais)
            self.assertEqual(serial["payload"], "{00002004:0000100000000000}\r\n")

    def test_liga_sem_setpoint_valido_nao_envia(self):
        for msg in (chirpstack(0, 5), chirpstack(0, 5, 0x01, 0x90)):   # nada / 400°
            serial, ultimo = self.enviar(msg)
            self.assertIsNone(serial)
            self.assertIn("NÃO enviado", ultimo["payload"])

    def test_deployer_com_a_mensagem_do_arquivo(self):
        serial, ultimo = self.enviar(chirpstack(0, 1))
        self.assertEqual(serial["payload"], "{00003008:0100000000000000}\r\n")
        self.assertIn("ACIONA DEPLOYER", ultimo["payload"])

    def test_deployer_sem_mensagem_nao_envia(self):
        serial, ultimo = self.enviar(chirpstack(0, 2))
        self.assertIsNone(serial)
        self.assertIn("não configurado", ultimo["payload"])

    def test_comando_desconhecido_nao_envia(self):
        for msg in (chirpstack(0, 3), {"payload": "texto qualquer"}):
            serial, _ = self.enviar(msg)
            self.assertIsNone(serial)


@unittest.skipUnless(shutil.which("node"), "precisa do Node.js")
class ComandoDoDashboardTest(unittest.TestCase):
    """Linha que o dashboard Python manda pela porta TCP 5555 -> serial."""

    def cmd(self, linha, ip="127.0.0.1"):
        return rodar(g.func_cmd_dashboard(CMDS), {"payload": linha, "ip": ip})

    def test_aceita_mensagens_do_arquivo_vindas_do_raspberry(self):
        for ip in ("127.0.0.1", "::1", "::ffff:127.0.0.1"):
            serial, ultimo = self.cmd("{00002004:80012C0000000000}\r", ip)
            self.assertEqual(serial["payload"], "{00002004:80012C0000000000}\r\n")
            self.assertIn("LIGA ATITUDE 300°", ultimo["payload"])
        serial, _ = self.cmd("{00002004:0000100000000000}")
        self.assertEqual(serial["payload"], "{00002004:0000100000000000}\r\n")
        serial, ultimo = self.cmd("{00003008:0100000000000000}")
        self.assertEqual(serial["payload"], "{00003008:0100000000000000}\r\n")
        self.assertIn("ACIONA DEPLOYER", ultimo["payload"])

    def test_recusa_de_outra_maquina(self):
        self.assertIsNone(self.cmd("{00002004:80012C0000000000}", ip="10.33.133.20"))

    def test_recusa_o_que_nao_esta_no_arquivo(self):
        for linha in ("{00002004:80019000000000000}",    # 17 dígitos
                      "{00002004:8001900000000000}",     # setpoint 400
                      "{00002004:4000100000000000}",     # status 40
                      "{00002004:8000100000000001}",     # bytes 3-7 não zerados
                      "{0001F864:8000100000000000}",     # outro ID
                      "{00003008:0200000000000000}",     # deployer não configurado
                      "", "texto qualquer"):
            self.assertIsNone(self.cmd(linha), linha)


if __name__ == "__main__":
    unittest.main()
