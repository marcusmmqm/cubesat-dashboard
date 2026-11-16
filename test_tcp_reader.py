import queue
import socket
import threading
import time
import unittest

from dashboard import TcpReader, parse_hostport


class TcpReaderTest(unittest.TestCase):
    def test_recebe_linhas_do_node_red(self):
        srv = socket.socket()
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        port = srv.getsockname()[1]

        def node_red():
            conn, _ = srv.accept()
            # linha partida em dois pedaços + uma linha que não é mensagem
            conn.sendall(b"{0001F864:007A0000")
            time.sleep(0.05)
            conn.sendall(b"00000000}\nCubesat online\n{000520B6:170A050301010000}\n")
            time.sleep(0.3)
            conn.close()

        threading.Thread(target=node_red, daemon=True).start()
        q = queue.Queue()
        r = TcpReader("127.0.0.1", port, q)
        r.start()
        try:
            a = q.get(timeout=3)
            b = q.get(timeout=3)
        finally:
            r.stop()
            srv.close()
        self.assertEqual(a[1:], (0x1F864, bytes.fromhex("007A000000000000")))
        self.assertEqual(b[1:], (0x520B6, bytes.fromhex("170A050301010000")))

    def test_parse_hostport(self):
        self.assertEqual(parse_hostport("localhost:5555"), ("localhost", 5555))
        self.assertEqual(parse_hostport(":5555"), ("localhost", 5555))


if __name__ == "__main__":
    unittest.main()
