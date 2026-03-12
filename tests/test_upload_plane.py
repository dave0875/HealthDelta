from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

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
