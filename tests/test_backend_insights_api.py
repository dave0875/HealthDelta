from __future__ import annotations

import json
import os
import stat
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


def _write_mixed_scope_ios_export_zip(path: Path) -> None:
    manifest = {
        "run_id": "run_20260314_000001",
        "files": [
            {"path": "ndjson/observations.ndjson", "size_bytes": 456, "sha256": "1" * 64},
        ],
        "row_counts": {"observations": 8},
    }
    observations = "\n".join(
        [
            json.dumps(
                {
                    "record_key": "hk-rate-1",
                    "canonical_person_id": "wellness-a",
                    "source": "healthkit",
                    "event_time": "2026-03-10T08:00:00Z",
                    "value_num": 72,
                    "unit": "count/min",
                },
                sort_keys=True,
            ),
            json.dumps(
                {
                    "record_key": "hk-rate-2",
                    "canonical_person_id": "wellness-a",
                    "source": "healthkit",
                    "event_time": "2026-03-12T08:00:00Z",
                    "value_num": 68,
                    "unit": "count/min",
                },
                sort_keys=True,
            ),
            json.dumps(
                {
                    "record_key": "hk-step-1",
                    "canonical_person_id": "wellness-b",
                    "source": "healthkit",
                    "event_time": "2026-03-11T09:00:00Z",
                    "value_num": 1200,
                    "unit": "count",
                },
                sort_keys=True,
            ),
            json.dumps(
                {
                    "record_key": "hk-cal-1",
                    "canonical_person_id": "wellness-b",
                    "source": "healthkit",
                    "event_time": "2026-03-13T09:00:00Z",
                    "value_num": 220,
                    "unit": "Cal",
                },
                sort_keys=True,
            ),
            json.dumps(
                {
                    "record_key": "fhir-spo2-1",
                    "canonical_person_id": "clinical-a",
                    "source": "fhir",
                    "event_time": "2026-03-12T10:00:00Z",
                    "display": "SpO2",
                    "value_num": 96,
                    "unit": "%",
                },
                sort_keys=True,
            ),
            json.dumps(
                {
                    "record_key": "fhir-hgb-1",
                    "canonical_person_id": "clinical-a",
                    "source": "fhir",
                    "event_time": "2026-03-11T10:00:00Z",
                    "display": "Hemoglobin [Mass/volume] in Blood",
                    "value_num": 8.1,
                    "unit": "g/dL",
                },
                sort_keys=True,
            ),
            json.dumps(
                {
                    "record_key": "fhir-plt-1",
                    "canonical_person_id": "clinical-a",
                    "source": "fhir",
                    "event_time": "2026-03-10T10:00:00Z",
                    "display": "Platelets [#/volume] in Blood by Automated count",
                    "value_num": 150,
                    "unit": "K/UL",
                },
                sort_keys=True,
            ),
            json.dumps(
                {
                    "record_key": "fhir-cr-1",
                    "canonical_person_id": "clinical-a",
                    "source": "fhir",
                    "event_time": "2026-03-09T10:00:00Z",
                    "display": "Creatinine [Mass/volume] in Serum or Plasma",
                    "value_num": 1.2,
                    "unit": "mg/dL",
                },
                sort_keys=True,
            ),
        ]
    ) + "\n"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("run_20260314_000001/manifest.json", json.dumps(manifest, sort_keys=True))
        archive.writestr("run_20260314_000001/ndjson/observations.ndjson", observations)


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
        self.assertEqual(payload["cards"][0]["title"], "Overview")
        self.assertEqual(payload["cards"][0]["sourceLabel"], "orin/analysis/overview")
        self.assertEqual(payload["cards"][0]["domain"], "combined")
        self.assertEqual(payload["cards"][1]["title"], "Fitness")
        self.assertEqual(payload["cards"][1]["sourceLabel"], "orin/analysis/fitness")
        self.assertEqual(payload["cards"][1]["domain"], "fitness")
        self.assertTrue((dataset_dir / "analysis" / "duckdb" / "run.duckdb").exists())
        self.assertTrue((dataset_dir / "analysis" / "reports" / "summary.md").exists())
        self.assertTrue((dataset_dir / "analysis" / "note" / "doctor_note.md").exists())

    def test_insights_current_clinical_card_uses_recent_clinical_happenings_from_note(self) -> None:
        plane = UploadPlane(Path(self._tmp.name))
        dataset_dir = Path(self._tmp.name) / "datasets" / "dataset_clinical"
        (dataset_dir / "analysis" / "reports").mkdir(parents=True, exist_ok=True)
        (dataset_dir / "analysis" / "note").mkdir(parents=True, exist_ok=True)
        dataset_dir.mkdir(parents=True, exist_ok=True)
        _write_ios_export_zip(dataset_dir / "export.zip")
        (dataset_dir / "analysis" / "reports" / "summary.json").write_text(
            json.dumps(
                {
                    "tables": {
                        "observations": {
                            "total_rows": 12,
                            "min_event_time": "2026-02-09T09:00:00Z",
                            "max_event_time": "2026-03-06T10:00:00Z",
                            "rows_by_source": {"ios": 12},
                        }
                    }
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        (dataset_dir / "analysis" / "reports" / "summary.md").write_text("summary\n", encoding="utf-8")
        (dataset_dir / "analysis" / "note" / "doctor_note.md").write_text(
            "\n".join(
                [
                    "HealthDelta Doctor's Note",
                    "run_id=dataset_clinical",
                    "generated_at=2026-03-06T10:00:00Z",
                    "",
                    "Summary",
                    "- Recent clinical activity spans 1 share-safe patient bucket across 4 active days in the latest 60-day window.",
                    "- Recent clinical themes included oxygenation monitoring, blood counts and differentials, serum chemistries, blood-bank and transfusion workflow.",
                    "- Highest recent clinical activity occurred on 2026-02-24 (3 rows), 2026-02-09 (3 rows), 2026-02-27 (3 rows).",
                    "",
                    "Facts",
                    "people=1",
                    "active_days=4",
                    "event_time_range=2026-02-09T09:00:00Z..2026-03-06T10:00:00Z",
                    "domain_mix=clinical",
                    "totals.observations=12",
                    "totals.documents=0",
                    "totals.medications=0",
                    "totals.conditions=0",
                    "totals.encounters=0",
                    "totals.procedures=0",
                    "totals.diagnostic_reports=0",
                    "sources.healthkit=0",
                    "sources.fhir=12",
                    "sources.cda=0",
                    "recent_clinical.patient_buckets=1",
                    "recent_clinical.active_days=4",
                    "recent_clinical.top_themes=oxygenation monitoring;blood counts and differentials;serum chemistries;blood-bank and transfusion workflow",
                    "recent_clinical.top_days=2026-02-24:3;2026-02-09:3;2026-02-27:3",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        plane._set_current_dataset("dataset_clinical")

        status, payload = self._request("GET", "/insights/current")
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "ok")
        clinical = [card for card in payload["cards"] if card["domain"] == "clinical"][0]
        self.assertIn("Recent clinical themes: oxygenation monitoring, blood counts and differentials, serum chemistries, blood-bank and transfusion workflow.", clinical["body"])
        self.assertIn("Highest recent clinical activity: 2026-02-24 (3 rows), 2026-02-09 (3 rows), 2026-02-27 (3 rows).", clinical["body"])

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
        self.assertEqual(payload["cards"][0]["domain"], "combined")
        self.assertIn("stable cadence", payload["cards"][0]["body"])
        self.assertEqual(ollama.request_count, 1)
        self.assertIsNotNone(ollama.last_request_json)
        self.assertIn("doctor_note", ollama.last_request_json["prompt"])
        self.assertIn("summary_json", ollama.last_request_json["prompt"])
        self.assertIn("Prioritize clinically or behaviorally meaningful findings", ollama.last_request_json["prompt"])

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
        self.assertEqual(payload["cards"][0]["title"], "Overview")
        self.assertEqual(payload["cards"][0]["sourceLabel"], "orin/analysis/overview")
        self.assertEqual(payload["cards"][0]["domain"], "combined")
        self.assertEqual(ollama.request_count, 1)

    def test_insights_current_falls_back_when_ollama_output_is_only_row_counts(self) -> None:
        plane = UploadPlane(Path(self._tmp.name))
        dataset_dir = Path(self._tmp.name) / "datasets" / "dataset_test"
        dataset_dir.mkdir(parents=True, exist_ok=True)
        _write_ios_export_zip(dataset_dir / "export.zip")
        plane._set_current_dataset("dataset_test")

        ollama = _FakeOllamaServer(
            status_code=200,
            body={
                "response": json.dumps(
                    {
                        "cards": [
                            {"title": "Fitness", "body": "28,872 rows.", "domain": "fitness"},
                            {"title": "Clinical", "body": "1,213 rows.", "domain": "clinical"},
                            {"title": "Overview", "body": "30,085 rows.", "domain": "combined"},
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
        self.assertEqual(payload["cards"][0]["sourceLabel"], "orin/analysis/overview")
        self.assertNotEqual(payload["cards"][0]["body"], "30,085 rows.")
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

        coverage_by_person = dataset_dir / "analysis" / "reports" / "coverage_by_person.csv"
        self.assertTrue(coverage_by_person.exists())
        self.assertEqual(stat.S_IMODE(coverage_by_person.stat().st_mode), 0o644)

    def test_patients_current_recovers_from_unreadable_coverage_csv(self) -> None:
        plane = UploadPlane(Path(self._tmp.name))
        dataset_dir = Path(self._tmp.name) / "datasets" / "dataset_test"
        dataset_dir.mkdir(parents=True, exist_ok=True)
        _write_ios_export_zip(dataset_dir / "export.zip")
        plane._set_current_dataset("dataset_test")

        status, _payload = self._request("GET", "/patients/current")
        self.assertEqual(status, 200)

        coverage_by_person = dataset_dir / "analysis" / "reports" / "coverage_by_person.csv"
        reports_dir = coverage_by_person.parent
        coverage_by_person.chmod(0)
        reports_dir.chmod(0o555)
        self.assertEqual(stat.S_IMODE(coverage_by_person.stat().st_mode), 0)

        status, payload = self._request("GET", "/patients/current")
        self.assertEqual(status, 200)
        self.assertEqual(payload["dataset"], "dataset_test")
        self.assertEqual(
            payload["patients"][0],
            {
                "canonical_person_id": "person-a",
                "display_label": "Patient 1",
                "row_count": 2,
                "min_event_time": "2026-03-01T00:00:00Z",
                "max_event_time": "2026-03-11T00:00:00Z",
            },
        )

        fallback_coverage = Path(self._tmp.name) / "runtime_cache" / "dataset_test" / "reports" / "coverage_by_person.csv"
        self.assertTrue(fallback_coverage.exists())
        self.assertEqual(stat.S_IMODE(fallback_coverage.stat().st_mode), 0o644)

    def test_insights_current_filters_by_window_days(self) -> None:
        plane = UploadPlane(Path(self._tmp.name))
        dataset_dir = Path(self._tmp.name) / "datasets" / "dataset_test"
        dataset_dir.mkdir(parents=True, exist_ok=True)
        _write_ios_export_zip(dataset_dir / "export.zip")
        plane._set_current_dataset("dataset_test")

        status, payload = self._request("GET", "/insights/current?window_days=3")
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "ok")
        self.assertIn("Evaluation window: last 3 days", payload["cards"][0]["body"])

    def test_insights_current_filtered_cards_summarize_real_fitness_and_clinical_signals(self) -> None:
        plane = UploadPlane(Path(self._tmp.name))
        dataset_dir = Path(self._tmp.name) / "datasets" / "dataset_mixed"
        dataset_dir.mkdir(parents=True, exist_ok=True)
        _write_mixed_scope_ios_export_zip(dataset_dir / "export.zip")
        plane._set_current_dataset("dataset_mixed")

        status, payload = self._request("GET", "/insights/current?window_days=30")
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "ok")

        by_domain = {card["domain"]: card for card in payload["cards"]}
        self.assertIn("fitness", by_domain)
        self.assertIn("clinical", by_domain)
        self.assertIn("Apple Health activity is present across 4 active days", by_domain["fitness"]["body"])
        self.assertIn("heart-rate-style telemetry", by_domain["fitness"]["body"])
        self.assertIn("step and activity counts", by_domain["fitness"]["body"])
        self.assertIn("energy expenditure", by_domain["fitness"]["body"])
        self.assertIn("Structured clinical monitoring", by_domain["clinical"]["body"])
        self.assertIn("oxygenation monitoring", by_domain["clinical"]["body"])
        self.assertIn("blood counts and differentials", by_domain["clinical"]["body"])
        self.assertIn("serum chemistries", by_domain["clinical"]["body"])

    def test_insights_current_filters_by_canonical_person_id(self) -> None:
        plane = UploadPlane(Path(self._tmp.name))
        dataset_dir = Path(self._tmp.name) / "datasets" / "dataset_test"
        dataset_dir.mkdir(parents=True, exist_ok=True)
        _write_ios_export_zip(dataset_dir / "export.zip")
        plane._set_current_dataset("dataset_test")

        status, payload = self._request("GET", "/insights/current?canonical_person_id=person-a")
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "ok")
        self.assertIn("Filtered to the requested patient.", payload["cards"][0]["body"])

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
