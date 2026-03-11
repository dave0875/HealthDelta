from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import unittest
import zipfile
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from healthdelta.backend_server import make_server
from healthdelta.upload_plane import UploadPlane


def _write_ios_export_zip(path: Path) -> None:
    manifest = {
        "run_id": "run_20260311_151707",
        "files": [
            {"path": "ndjson/observations.ndjson", "size_bytes": 123, "sha256": "0" * 64},
        ],
        "row_counts": {"observations": 2},
    }
    observations = "\n".join(
        [
            json.dumps(
                {
                    "record_key": "rk1",
                    "source": "healthkit",
                    "sample_type": "HKQuantityTypeIdentifierStepCount",
                    "start_time": "2026-03-10T00:00:00Z",
                    "end_time": "2026-03-10T00:15:00Z",
                    "value_num": 1200,
                    "unit": "count",
                },
                sort_keys=True,
            ),
            json.dumps(
                {
                    "record_key": "rk2",
                    "source": "healthkit",
                    "sample_type": "HKQuantityTypeIdentifierStepCount",
                    "start_time": "2026-03-11T00:00:00Z",
                    "end_time": "2026-03-11T00:15:00Z",
                    "value_num": 800,
                    "unit": "count",
                },
                sort_keys=True,
            ),
        ]
    ) + "\n"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("run_20260311_151707/manifest.json", json.dumps(manifest, sort_keys=True))
        archive.writestr("run_20260311_151707/ndjson/observations.ndjson", observations)


class TestBackendInsightsAPI(unittest.TestCase):
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

    def _request(self, method: str, path: str, *, auth: bool = True) -> tuple[int, dict]:
        headers: dict[str, str] = {}
        if auth:
            headers["Authorization"] = "Bearer test-token"
        req = Request(self.base_url + path, headers=headers, method=method)
        try:
            with urlopen(req) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except HTTPError as err:
            return err.code, json.loads(err.read().decode("utf-8"))

    def test_insights_current_returns_no_insights_yet_without_dataset(self) -> None:
        status, payload = self._request("GET", "/insights/current")
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "no_insights_yet")
        self.assertEqual(payload["cards"], [])

    def test_insights_current_returns_generated_cards_for_current_dataset(self) -> None:
        plane = UploadPlane(Path(self._tmp.name))
        dataset_dir = Path(self._tmp.name) / "datasets" / "dataset_test"
        dataset_dir.mkdir(parents=True, exist_ok=True)
        _write_ios_export_zip(dataset_dir / "export.zip")
        plane._set_current_dataset("dataset_test")

        status, payload = self._request("GET", "/insights/current")
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["dataset"], "dataset_test")
        self.assertEqual(len(payload["cards"]), 2)
        self.assertEqual(payload["cards"][0]["title"], "ORIN Overview")
        self.assertIn("Observation rows: 2.", payload["cards"][0]["body"])
        self.assertEqual(payload["cards"][1]["title"], "Activity Snapshot")
        self.assertIn("2,000", payload["cards"][1]["body"])

    def test_insights_current_rejects_invalid_bearer(self) -> None:
        status, payload = self._request("GET", "/insights/current", auth=False)
        self.assertEqual(status, 401)
        self.assertEqual(payload["error"], "unauthorized")


if __name__ == "__main__":
    unittest.main()
