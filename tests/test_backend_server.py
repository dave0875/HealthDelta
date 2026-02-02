import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from urllib.request import Request, urlopen


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

    def test_summary_vertical_slice(self) -> None:
        server, thread, base_url = self._start_server()
        try:
            with tempfile.TemporaryDirectory() as td:
                payload = json.dumps(
                    {
                        "input_path": str((Path("tests/fixtures/profile_export")).resolve()),
                        "work_dir": str((Path(td) / "work").resolve()),
                        "citation_limit": 8,
                    }
                ).encode("utf-8")
                req = Request(base_url + "/summary", data=payload, headers={"Content-Type": "application/json"}, method="POST")
                with urlopen(req) as resp:
                    self.assertEqual(resp.status, 200)
                    obj = json.loads(resp.read().decode("utf-8"))
                    self.assertTrue(obj.get("ok"))
                    self.assertIn("summary", obj)
                    self.assertIn("citations", obj)
                    self.assertGreater(len(obj["citations"]), 0)
                    blob = json.dumps(obj, sort_keys=True)
                    self.assertNotIn("John", blob)
                    self.assertNotIn("Doe", blob)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_summary_requires_input_path(self) -> None:
        server, thread, base_url = self._start_server()
        try:
            payload = json.dumps({"work_dir": "tmp"}).encode("utf-8")
            req = Request(base_url + "/summary", data=payload, headers={"Content-Type": "application/json"}, method="POST")
            try:
                urlopen(req)
                self.fail("expected HTTP error")
            except Exception as e:
                body = getattr(e, "read", lambda: b"")().decode("utf-8")
                self.assertIn("input_path_required", body)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
