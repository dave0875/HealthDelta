import json
import threading
import time
import unittest
from urllib.request import urlopen


class TestBackendServer(unittest.TestCase):
    def _start_server(self):
        from healthdelta.backend_server import make_server

        server = make_server(host="127.0.0.1", port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        # small readiness wait (local loopback)
        time.sleep(0.05)
        host, port = server.server_address
        base_url = f"http://{host}:{port}"
        return server, thread, base_url

    def test_healthz(self) -> None:
        server, thread, base_url = self._start_server()
        try:
            with urlopen(base_url + "/healthz") as resp:
                self.assertEqual(resp.status, 200)
                obj = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(obj.get("ok"), True)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_version(self) -> None:
        server, thread, base_url = self._start_server()
        try:
            with urlopen(base_url + "/version") as resp:
                self.assertEqual(resp.status, 200)
                obj = json.loads(resp.read().decode("utf-8"))
                self.assertIn("version", obj)
                self.assertIn("git_sha", obj)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
