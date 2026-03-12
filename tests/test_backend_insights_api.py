from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import unittest
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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
                    "canonical_person_id": "person-a",
                    "source": "healthkit",
                    "sample_type": "HKQuantityTypeIdentifierStepCount",
                    "start_time": "2026-03-01T00:00:00Z",
                    "end_time": "2026-03-01T00:15:00Z",
                    "value_num": 1200,
                    "unit": "count",
                },
                sort_keys=True,
            ),
            json.dumps(
                {
                    "record_key": "rk2",
                    "canonical_person_id": "person-a",
                    "source": "healthkit",
                    "sample_type": "HKQuantityTypeIdentifierStepCount",
                    "start_time": "2026-03-11T00:00:00Z",
                    "end_time": "2026-03-11T00:15:00Z",
                    "value_num": 800,
                    "unit": "count",
                },
                sort_keys=True,
            ),
            json.dumps(
                {
                    "record_key": "rk3",
                    "canonical_person_id": "person-b",
                    "source": "healthkit",
                    "sample_type": "HKQuantityTypeIdentifierStepCount",
                    "start_time": "2026-03-11T12:00:00Z",
                    "end_time": "2026-03-11T12:15:00Z",
                    "value_num": 600,
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
        self._old_ollama_base = os.environ.get("HEALTHDELTA_OLLAMA_BASE_URL")
        self._old_ollama_model = os.environ.get("HEALTHDELTA_OLLAMA_MODEL")
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
        if self._old_ollama_base is None:
            os.environ.pop("HEALTHDELTA_OLLAMA_BASE_URL", None)
        else:
            os.environ["HEALTHDELTA_OLLAMA_BASE_URL"] = self._old_ollama_base
        if self._old_ollama_model is None:
            os.environ.pop("HEALTHDELTA_OLLAMA_MODEL", None)
        else:
            os.environ["HEALTHDELTA_OLLAMA_MODEL"] = self._old_ollama_model

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
        self.assertEqual(payload["cards"][0]["title"], "Doctor's Note")
        self.assertEqual(payload["cards"][0]["sourceLabel"], "orin/analysis/note")
        self.assertEqual(payload["cards"][1]["title"], "Summary")
        self.assertEqual(payload["cards"][1]["sourceLabel"], "orin/analysis/reports")
        self.assertTrue((dataset_dir / "analysis" / "duckdb" / "run.duckdb").exists())
        self.assertTrue((dataset_dir / "analysis" / "reports" / "summary.md").exists())
        self.assertTrue((dataset_dir / "analysis" / "note" / "doctor_note.md").exists())

    def test_insights_current_prefers_ollama_refined_cards_when_available(self) -> None:
        plane = UploadPlane(Path(self._tmp.name))
        dataset_dir = Path(self._tmp.name) / "datasets" / "dataset_test"
        dataset_dir.mkdir(parents=True, exist_ok=True)
        _write_ios_export_zip(dataset_dir / "export.zip")
        plane._set_current_dataset("dataset_test")

        ollama = _FakeOllamaServer(
            status_code=200,
            body={
                "response": "Here is the JSON payload:\n"
                + json.dumps(
                    {
                        "cards": [
                            {
                                "title": "Activity Pattern",
                                "body": "You logged activity on 2 distinct days with a stable cadence across the upload window.",
                            },
                            {
                                "title": "Coaching Note",
                                "body": "The latest upload suggests a small sample so trend confidence is limited, but consistency is improving.",
                            },
                        ]
                    },
                    sort_keys=True,
                )
            },
        )
        ollama.start()
        self.addCleanup(ollama.stop)
        os.environ["HEALTHDELTA_OLLAMA_BASE_URL"] = ollama.base_url
        os.environ["HEALTHDELTA_OLLAMA_MODEL"] = "llama3.2:latest"

        status, payload = self._request("GET", "/insights/current")
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual([card["title"] for card in payload["cards"]], ["Activity Pattern", "Coaching Note"])
        self.assertEqual(payload["cards"][0]["sourceLabel"], "orin/ollama")
        self.assertIn("stable cadence", payload["cards"][0]["body"])
        self.assertEqual(ollama.request_count, 1)
        self.assertIsNotNone(ollama.last_request_json)
        self.assertIn("doctor_note", ollama.last_request_json["prompt"])
        self.assertIn("summary_json", ollama.last_request_json["prompt"])

    def test_insights_current_falls_back_when_ollama_output_is_invalid(self) -> None:
        plane = UploadPlane(Path(self._tmp.name))
        dataset_dir = Path(self._tmp.name) / "datasets" / "dataset_test"
        dataset_dir.mkdir(parents=True, exist_ok=True)
        _write_ios_export_zip(dataset_dir / "export.zip")
        plane._set_current_dataset("dataset_test")

        ollama = _FakeOllamaServer(status_code=200, body={"response": "not-json"})
        ollama.start()
        self.addCleanup(ollama.stop)
        os.environ["HEALTHDELTA_OLLAMA_BASE_URL"] = ollama.base_url
        os.environ["HEALTHDELTA_OLLAMA_MODEL"] = "llama3.2:latest"

        status, payload = self._request("GET", "/insights/current")
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["cards"][0]["title"], "Doctor's Note")
        self.assertEqual(payload["cards"][0]["sourceLabel"], "orin/analysis/note")
        self.assertEqual(ollama.request_count, 1)

    def test_insights_current_rejects_invalid_bearer(self) -> None:
        status, payload = self._request("GET", "/insights/current", auth=False)
        self.assertEqual(status, 401)
        self.assertEqual(payload["error"], "unauthorized")

    def test_patients_current_returns_share_safe_scope_options_for_current_dataset(self) -> None:
        plane = UploadPlane(Path(self._tmp.name))
        dataset_dir = Path(self._tmp.name) / "datasets" / "dataset_test"
        dataset_dir.mkdir(parents=True, exist_ok=True)
        _write_ios_export_zip(dataset_dir / "export.zip")
        plane._set_current_dataset("dataset_test")

        status, payload = self._request("GET", "/patients/current")
        self.assertEqual(status, 200)
        self.assertEqual(payload["dataset"], "dataset_test")
        self.assertEqual(
            payload["patients"],
            [
                {
                    "canonical_person_id": "person-a",
                    "display_label": "Patient 1",
                    "row_count": 2,
                    "min_event_time": "2026-03-01T00:00:00Z",
                    "max_event_time": "2026-03-11T00:00:00Z",
                },
                {
                    "canonical_person_id": "person-b",
                    "display_label": "Patient 2",
                    "row_count": 1,
                    "min_event_time": "2026-03-11T12:00:00Z",
                    "max_event_time": "2026-03-11T12:00:00Z",
                },
            ],
        )

    def test_insights_current_filters_by_window_days(self) -> None:
        plane = UploadPlane(Path(self._tmp.name))
        dataset_dir = Path(self._tmp.name) / "datasets" / "dataset_test"
        dataset_dir.mkdir(parents=True, exist_ok=True)
        _write_ios_export_zip(dataset_dir / "export.zip")
        plane._set_current_dataset("dataset_test")

        status, payload = self._request("GET", "/insights/current?window_days=3")
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "ok")
        self.assertIn("2 observation rows", payload["cards"][0]["body"])

    def test_insights_current_filters_by_canonical_person_id(self) -> None:
        plane = UploadPlane(Path(self._tmp.name))
        dataset_dir = Path(self._tmp.name) / "datasets" / "dataset_test"
        dataset_dir.mkdir(parents=True, exist_ok=True)
        _write_ios_export_zip(dataset_dir / "export.zip")
        plane._set_current_dataset("dataset_test")

        status, payload = self._request("GET", "/insights/current?canonical_person_id=person-a")
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "ok")
        self.assertIn("2 observation rows", payload["cards"][0]["body"])

    def test_insights_current_returns_no_insights_yet_for_empty_filter_match(self) -> None:
        plane = UploadPlane(Path(self._tmp.name))
        dataset_dir = Path(self._tmp.name) / "datasets" / "dataset_test"
        dataset_dir.mkdir(parents=True, exist_ok=True)
        _write_ios_export_zip(dataset_dir / "export.zip")
        plane._set_current_dataset("dataset_test")

        status, payload = self._request("GET", "/insights/current?canonical_person_id=missing-person")
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "no_insights_yet")
        self.assertEqual(payload["cards"], [])


class _FakeOllamaHandler(BaseHTTPRequestHandler):
    status_code = 200
    body: dict[str, object] = {"response": "{}"}
    request_count = 0
    last_request_json: dict[str, object] | None = None

    def do_POST(self) -> None:  # noqa: N802
        type(self).request_count += 1
        if self.path != "/api/generate":
            self.send_response(404)
            self.end_headers()
            return
        raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        try:
            type(self).last_request_json = json.loads(raw.decode("utf-8"))
        except Exception:
            type(self).last_request_json = None
        payload = json.dumps(type(self).body).encode("utf-8")
        self.send_response(type(self).status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return


class _FakeOllamaServer:
    def __init__(self, *, status_code: int, body: dict[str, object]) -> None:
        self._handler = type(
            "_CaseSpecificOllamaHandler",
            (_FakeOllamaHandler,),
            {"status_code": status_code, "body": body, "request_count": 0, "last_request_json": None},
        )
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        host, port = self._server.server_address
        return f"http://{host}:{port}"

    @property
    def request_count(self) -> int:
        return int(self._handler.request_count)

    @property
    def last_request_json(self) -> dict[str, object] | None:
        value = self._handler.last_request_json
        return value if isinstance(value, dict) else None

    def start(self) -> None:
        self._thread.start()
        time.sleep(0.05)

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
