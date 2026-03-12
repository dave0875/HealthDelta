from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import duckdb

from healthdelta.upload_plane import UploadPlane


def _write_ios_export_zip(path: Path, *, run_id: str, rows: list[dict[str, object]]) -> bytes:
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
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(f"{run_id}/manifest.json", json.dumps(manifest, sort_keys=True))
        archive.writestr(f"{run_id}/ndjson/observations.ndjson", observations)
    return path.read_bytes()


def _read_current_ios_dataset(export_zip: Path) -> tuple[dict[str, object], list[dict[str, object]]]:
    with tempfile.TemporaryDirectory() as tmp:
        extract_root = Path(tmp)
        with zipfile.ZipFile(export_zip, "r") as archive:
            archive.extractall(extract_root)
        manifest_path = next(extract_root.rglob("manifest.json"))
        observations_path = manifest_path.parent / "ndjson" / "observations.ndjson"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        rows = [
            json.loads(line)
            for line in observations_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        return manifest, rows


def _seed_bootstrap_current_dataset(
    plane: UploadPlane,
    *,
    dataset_name: str,
    rows: list[dict[str, object]],
) -> None:
    dataset_dir = plane.datasets_root / dataset_name
    dataset_dir.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(dataset_dir / "export.zip", "w") as archive:
        archive.writestr("apple/export.xml", "<HealthData></HealthData>")

    analysis_db = dataset_dir / "analysis" / "duckdb" / "run.duckdb"
    analysis_db.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(analysis_db))
    try:
        con.execute(
            """
            CREATE TABLE observations (
              schema_version INTEGER,
              record_key VARCHAR,
              canonical_person_id VARCHAR,
              source VARCHAR,
              source_system VARCHAR,
              source_file VARCHAR,
              event_time TIMESTAMP,
              run_id VARCHAR,
              event_key VARCHAR,
              source_id VARCHAR,
              record_id VARCHAR,
              record_type VARCHAR,
              observation_id VARCHAR,
              subject_reference VARCHAR,
              encounter_id VARCHAR,
              effective_start TIMESTAMP,
              effective_end TIMESTAMP,
              hk_type VARCHAR,
              sample_kind VARCHAR,
              resource_type VARCHAR,
              code_system VARCHAR,
              code VARCHAR,
              display VARCHAR,
              value VARCHAR,
              value_num DOUBLE,
              value_text VARCHAR,
              category_value INTEGER,
              activity_type VARCHAR,
              duration_seconds DOUBLE,
              total_energy_burned_num DOUBLE,
              total_energy_burned_unit VARCHAR,
              total_distance_num DOUBLE,
              total_distance_unit VARCHAR,
              unit VARCHAR,
              section_code VARCHAR,
              section_display VARCHAR,
              section_title VARCHAR,
              components_json VARCHAR,
              code_coding_json VARCHAR,
              type_coding_json VARCHAR,
              status VARCHAR
            )
            """
        )
        con.executemany(
            """
            INSERT INTO observations VALUES (
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                [
                    row.get("schema_version"),
                    row.get("record_key"),
                    row.get("canonical_person_id"),
                    row.get("source"),
                    row.get("source_system"),
                    row.get("source_file"),
                    row.get("event_time"),
                    row.get("run_id"),
                    row.get("event_key"),
                    row.get("source_id"),
                    row.get("record_id"),
                    row.get("record_type"),
                    row.get("observation_id"),
                    row.get("subject_reference"),
                    row.get("encounter_id"),
                    row.get("effective_start"),
                    row.get("effective_end"),
                    row.get("hk_type"),
                    row.get("sample_kind"),
                    row.get("resource_type"),
                    row.get("code_system"),
                    row.get("code"),
                    row.get("display"),
                    row.get("value"),
                    row.get("value_num"),
                    row.get("value_text"),
                    row.get("category_value"),
                    row.get("activity_type"),
                    row.get("duration_seconds"),
                    row.get("total_energy_burned_num"),
                    row.get("total_energy_burned_unit"),
                    row.get("total_distance_num"),
                    row.get("total_distance_unit"),
                    row.get("unit"),
                    row.get("section_code"),
                    row.get("section_display"),
                    row.get("section_title"),
                    row.get("components_json"),
                    row.get("code_coding_json"),
                    row.get("type_coding_json"),
                    row.get("status"),
                ]
                for row in rows
            ],
        )
    finally:
        con.close()

    plane._set_current_dataset(dataset_name)


class TestUploadPlane(unittest.TestCase):
    def test_session_bookkeeping_and_finalize(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plane = UploadPlane(Path(tmp))
            payload = b"abc123xyz"
            sha = hashlib.sha256(payload).hexdigest()
            session = plane.create_session(total_size=len(payload), sha256=sha)
            sid = session["id"]

            plane.put_chunk(sid, 0, b"abc")
            plane.put_chunk(sid, 1, b"123xyz")
            status = plane.get_session(sid)
            self.assertEqual(status["received_chunks"], [0, 1])
            self.assertEqual(status["received_bytes"], len(payload))

            finalized = plane.finalize_session(sid)
            dataset = finalized["finalized_dataset"]
            self.assertIsNotNone(dataset)

            current = plane.get_current_dataset()
            self.assertEqual(current["dataset"], dataset)
            export_zip = Path(current["export_zip"])
            self.assertTrue(export_zip.exists())
            self.assertEqual(export_zip.read_bytes(), payload)

    def test_finalize_session_accumulates_ios_exports_and_preserves_raw_uploads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plane = UploadPlane(Path(tmp))
            first_zip = Path(tmp) / "first.zip"
            second_zip = Path(tmp) / "second.zip"
            first_payload = _write_ios_export_zip(
                first_zip,
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
            second_payload = _write_ios_export_zip(
                second_zip,
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

            session1 = plane.create_session(
                total_size=len(first_payload),
                sha256=hashlib.sha256(first_payload).hexdigest(),
            )
            plane.put_chunk(session1["id"], 0, first_payload)
            plane.finalize_session(session1["id"])

            session2 = plane.create_session(
                total_size=len(second_payload),
                sha256=hashlib.sha256(second_payload).hexdigest(),
            )
            plane.put_chunk(session2["id"], 0, second_payload)
            finalized = plane.finalize_session(session2["id"])
            self.assertIsNotNone(finalized["finalized_dataset"])

            current = plane.get_current_dataset()
            manifest, rows = _read_current_ios_dataset(Path(current["export_zip"]))
            self.assertEqual(manifest["row_counts"], {"observations": 3})
            self.assertEqual([row["record_key"] for row in rows], ["rk1", "rk2", "rk3"])

            raw_uploads = sorted((Path(current["path"]) / "raw_uploads").glob("*.zip"))
            self.assertEqual(len(raw_uploads), 2)

    def test_finalize_session_dedupes_reuploaded_ios_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plane = UploadPlane(Path(tmp))
            export_zip = Path(tmp) / "run.zip"
            payload = _write_ios_export_zip(
                export_zip,
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
                    }
                ],
            )

            for _ in range(2):
                session = plane.create_session(
                    total_size=len(payload),
                    sha256=hashlib.sha256(payload).hexdigest(),
                )
                plane.put_chunk(session["id"], 0, payload)
                plane.finalize_session(session["id"])

            current = plane.get_current_dataset()
            manifest, rows = _read_current_ios_dataset(Path(current["export_zip"]))
            self.assertEqual(manifest["row_counts"], {"observations": 1})
            self.assertEqual([row["record_key"] for row in rows], ["rk1"])
            raw_uploads = sorted((Path(current["path"]) / "raw_uploads").glob("*.zip"))
            self.assertEqual(len(raw_uploads), 1)

    def test_finalize_session_accumulates_ios_delta_on_bootstrap_current_dataset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plane = UploadPlane(Path(tmp))
            _seed_bootstrap_current_dataset(
                plane,
                dataset_name="dataset_bootstrap",
                rows=[
                    {
                        "schema_version": 1,
                        "record_key": "rk1",
                        "canonical_person_id": "patient-a",
                        "source": "ios",
                        "event_time": "2026-03-10 00:15:00",
                        "run_id": "bootstrap-run",
                        "event_key": "rk1",
                        "source_id": "HKSample/bootstrap-1",
                        "effective_start": "2026-03-10 00:00:00",
                        "effective_end": "2026-03-10 00:15:00",
                        "hk_type": "HKQuantityTypeIdentifierStepCount",
                        "sample_kind": "quantity",
                        "display": "Steps",
                        "value": "10.0",
                        "value_num": 10.0,
                        "unit": "count",
                    },
                    {
                        "schema_version": 1,
                        "record_key": "rk2",
                        "canonical_person_id": "patient-b",
                        "source": "ios",
                        "event_time": "2026-03-10 01:15:00",
                        "run_id": "bootstrap-run",
                        "event_key": "rk2",
                        "source_id": "HKSample/bootstrap-2",
                        "effective_start": "2026-03-10 01:00:00",
                        "effective_end": "2026-03-10 01:15:00",
                        "hk_type": "HKQuantityTypeIdentifierHeartRate",
                        "sample_kind": "quantity",
                        "display": "Heart Rate",
                        "value": "70.0",
                        "value_num": 70.0,
                        "unit": "count/min",
                    },
                ],
            )

            delta_zip = Path(tmp) / "delta.zip"
            delta_payload = _write_ios_export_zip(
                delta_zip,
                run_id="run_delta",
                rows=[
                    {
                        "schema_version": 1,
                        "record_key": "rk2",
                        "canonical_person_id": "patient-b",
                        "source": "healthkit",
                        "source_id": "HKSample/bootstrap-2",
                        "sample_type": "HKQuantityTypeIdentifierHeartRate",
                        "start_time": "2026-03-10T01:00:00Z",
                        "end_time": "2026-03-10T01:15:00Z",
                        "value_num": 70,
                        "unit": "count/min",
                    },
                    {
                        "schema_version": 1,
                        "record_key": "rk3",
                        "canonical_person_id": "patient-c",
                        "source": "healthkit",
                        "source_id": "HKSample/delta-3",
                        "sample_type": "HKCategoryTypeIdentifierSleepAnalysis",
                        "sample_kind": "category",
                        "start_time": "2026-03-11T00:00:00Z",
                        "end_time": "2026-03-11T07:00:00Z",
                        "category_value": 1,
                    },
                ],
            )

            session = plane.create_session(
                total_size=len(delta_payload),
                sha256=hashlib.sha256(delta_payload).hexdigest(),
            )
            plane.put_chunk(session["id"], 0, delta_payload)
            plane.finalize_session(session["id"])

            current = plane.get_current_dataset()
            manifest, rows = _read_current_ios_dataset(Path(current["export_zip"]))
            self.assertEqual(manifest["row_counts"], {"observations": 3})
            self.assertEqual([row["record_key"] for row in rows], ["rk1", "rk2", "rk3"])
            self.assertEqual(
                manifest["source_runs"],
                [
                    {"run_id": "dataset_bootstrap", "raw_upload_sha256": ""},
                    {"run_id": "run_delta", "raw_upload_sha256": hashlib.sha256(delta_payload).hexdigest()},
                ],
            )

    def test_archive_current_clears_pointer_and_lists_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plane = UploadPlane(Path(tmp))
            session = plane.create_session(total_size=4, sha256=hashlib.sha256(b"data").hexdigest())
            sid = session["id"]
            plane.put_chunk(sid, 0, b"data")
            plane.finalize_session(sid)

            archived = plane.archive_current()
            self.assertIn("archive_", archived["archive"])
            archives = plane.list_archives()
            self.assertEqual(len(archives), 1)
            self.assertTrue(archives[0]["has_export_zip"])


if __name__ == "__main__":
    unittest.main()
