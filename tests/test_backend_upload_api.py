from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from healthdelta.backend_server import make_server


class TestBackendUploadAPI(unittest.TestCase):
    def setUp(self) -> None:
        self._old_data = os.environ.get("HEALTHDELTA_DATA_DIR")
        self._old_token = os.environ.get("HEALTHDELTA_UPLOAD_TOKEN")
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["HEALTHDELTA_DATA_DIR"] = self._tmp.name
        os.environ["HEALTHDELTA_UPLOAD_TOKEN"] = "test-token"
        self.server = make_server(host="127.0.0.1", port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        time.sleep(0.05)
        host, port = self.server.server_address
        self.base_url = f"http://{host}:{port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self._tmp.cleanup()
        if self._old_data is None:
            os.environ.pop("HEALTHDELTA_DATA_DIR", None)
        else:
            os.environ["HEALTHDELTA_DATA_DIR"] = self._old_data
        if self._old_token is None:
            os.environ.pop("HEALTHDELTA_UPLOAD_TOKEN", None)
        else:
            os.environ["HEALTHDELTA_UPLOAD_TOKEN"] = self._old_token

    def _request(self, method: str, path: str, *, body: bytes | None = None, auth: bool = True) -> tuple[int, dict]:
        headers: dict[str, str] = {}
        if auth:
            headers["Authorization"] = "Bearer test-token"
        if body is not None and method != "PUT":
            headers["Content-Type"] = "application/json"
        req = Request(self.base_url + path, data=body, headers=headers, method=method)
        try:
            with urlopen(req) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except HTTPError as err:
            payload = json.loads(err.read().decode("utf-8"))
            return err.code, payload

    def test_upload_finalize_archive_flow(self) -> None:
        payload = b"hello-" + b"world"
        sha = hashlib.sha256(payload).hexdigest()
        status, created = self._request(
            "POST",
            "/upload-sessions",
            body=json.dumps({"total_size": len(payload), "sha256": sha}).encode("utf-8"),
        )
        self.assertEqual(status, 201)
        sid = created["id"]

        st0, _ = self._request("PUT", f"/upload-sessions/{sid}/chunks/0", body=b"hello-")
        self.assertEqual(st0, 200)
        st1, _ = self._request("PUT", f"/upload-sessions/{sid}/chunks/1", body=b"world")
        self.assertEqual(st1, 200)

        st_status, session_state = self._request("GET", f"/upload-sessions/{sid}")
        self.assertEqual(st_status, 200)
        self.assertEqual(session_state["received_chunks"], [0, 1])

        st_fin, finalized = self._request("POST", f"/upload-sessions/{sid}/finalize", body=b"{}")
        self.assertEqual(st_fin, 200)
        self.assertEqual(finalized["status"], "finalized")

        st_curr, current = self._request("GET", "/datasets/current")
        self.assertEqual(st_curr, 200)
        self.assertTrue(current["dataset"].startswith("dataset_"))

        st_arch, archived = self._request("POST", "/datasets/archive", body=b"{}")
        self.assertEqual(st_arch, 200)
        self.assertTrue(archived["archive"].startswith("archive_"))

        st_list, archives = self._request("GET", "/datasets/archives")
        self.assertEqual(st_list, 200)
        self.assertEqual(len(archives["archives"]), 1)

    def test_upload_endpoints_reject_when_token_missing(self) -> None:
        os.environ.pop("HEALTHDELTA_UPLOAD_TOKEN", None)
        status, payload = self._request("GET", "/datasets/archives", auth=False)
        self.assertEqual(status, 503)
        self.assertEqual(payload["error"], "upload_unavailable")


if __name__ == "__main__":
    unittest.main()
