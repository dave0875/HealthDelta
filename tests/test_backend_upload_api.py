from __future__ import annotations

import hashlib
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


def _write_ios_export_bytes(*, run_id: str, rows: list[dict[str, object]]) -> bytes:
    observations = "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n"
    manifest = {
        "run_id": run_id,
        "files": [
            {
                "path": "ndjson/observations.ndjson",
                "size_bytes": len(observations.encode("utf-8")),
                "sha256": hashlib.sha256(observations.encode("utf-8")).hexdigest(),
            }
        ],
        "row_counts": {"observations": len(rows)},
    }
    path = Path(tempfile.mkdtemp()) / f"{run_id}.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(f"{run_id}/manifest.json", json.dumps(manifest, sort_keys=True))
        archive.writestr(f"{run_id}/ndjson/observations.ndjson", observations)
    payload = path.read_bytes()
    path.unlink()
    path.parent.rmdir()
    return payload


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

    def test_upload_finalize_accumulates_ios_current_dataset(self) -> None:
        first_payload = _write_ios_export_bytes(
            run_id="run_1",
            rows=[
                {
                    "schema_version": 1,
                    "record_key": "rk1",
                    "canonical_person_id": "person-1",
                    "source": "healthkit",
                    "source_id": "HKSample/uuid-1",
                    "sample_type": "HKQuantityTypeIdentifierStepCount",
                    "start_time": "2026-03-10T00:00:00Z",
                    "end_time": "2026-03-10T00:15:00Z",
                    "value_num": 10,
                    "unit": "count",
                },
                {
                    "schema_version": 1,
                    "record_key": "rk2",
                    "canonical_person_id": "person-1",
                    "source": "healthkit",
                    "source_id": "HKSample/uuid-2",
                    "sample_type": "HKQuantityTypeIdentifierStepCount",
                    "start_time": "2026-03-10T01:00:00Z",
                    "end_time": "2026-03-10T01:15:00Z",
                    "value_num": 20,
                    "unit": "count",
                },
            ],
        )
        second_payload = _write_ios_export_bytes(
            run_id="run_2",
            rows=[
                {
                    "schema_version": 1,
                    "record_key": "rk2",
                    "canonical_person_id": "person-1",
                    "source": "healthkit",
                    "source_id": "HKSample/uuid-2",
                    "sample_type": "HKQuantityTypeIdentifierStepCount",
                    "start_time": "2026-03-10T01:00:00Z",
                    "end_time": "2026-03-10T01:15:00Z",
                    "value_num": 20,
                    "unit": "count",
                },
                {
                    "schema_version": 1,
                    "record_key": "rk3",
                    "canonical_person_id": "person-1",
                    "source": "healthkit",
                    "source_id": "HKSample/uuid-3",
                    "sample_type": "HKQuantityTypeIdentifierStepCount",
                    "start_time": "2026-03-11T00:00:00Z",
                    "end_time": "2026-03-11T00:15:00Z",
                    "value_num": 30,
                    "unit": "count",
                },
            ],
        )

        def upload_and_finalize(payload: bytes) -> None:
            sha = hashlib.sha256(payload).hexdigest()
            status, created = self._request(
                "POST",
                "/upload-sessions",
                body=json.dumps({"total_size": len(payload), "sha256": sha}).encode("utf-8"),
            )
            self.assertEqual(status, 201)
            sid = created["id"]
            put_status, _ = self._request("PUT", f"/upload-sessions/{sid}/chunks/0", body=payload)
            self.assertEqual(put_status, 200)
            fin_status, finalized = self._request("POST", f"/upload-sessions/{sid}/finalize", body=b"{}")
            self.assertEqual(fin_status, 200)
            self.assertEqual(finalized["status"], "finalized")

        upload_and_finalize(first_payload)
        upload_and_finalize(second_payload)

        current_status, current = self._request("GET", "/datasets/current")
        self.assertEqual(current_status, 200)
        export_zip = Path(current["export_zip"])
        with tempfile.TemporaryDirectory() as tmp:
            with zipfile.ZipFile(export_zip, "r") as archive:
                archive.extractall(tmp)
            manifest_path = next(Path(tmp).rglob("manifest.json"))
            observations_path = manifest_path.parent / "ndjson" / "observations.ndjson"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            rows = [
                json.loads(line)
                for line in observations_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        self.assertEqual(manifest["row_counts"], {"observations": 3})
        self.assertEqual([row["record_key"] for row in rows], ["rk1", "rk2", "rk3"])

        insights_status, insights = self._request("GET", "/insights/current")
        self.assertEqual(insights_status, 200)
        self.assertEqual(insights["status"], "ok")
        self.assertIn("3 observation rows", insights["cards"][0]["body"])


if __name__ == "__main__":
    unittest.main()
