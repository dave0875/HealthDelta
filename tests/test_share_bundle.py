import io
import json
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class TestShareBundle(unittest.TestCase):
    def test_share_bundle_is_deterministic_and_excludes_staging(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            base_out = root / "out"
            run_id = "run123"
            run_root = base_out / run_id
            run_root.mkdir(parents=True, exist_ok=True)

            # Allowlisted dirs/files.
            _write(run_root / "ndjson" / "observations.ndjson", '{"canonical_person_id":"p1","source":"fhir","source_file":"x","event_time":"t","run_id":"r"}\n')
            _write(run_root / "duckdb" / "run.duckdb", "DUCKDB_BYTES")
            _write(run_root / "reports" / "summary.json", "{}\n")
            _write(run_root / "note" / "doctor_note.txt", "HealthDelta Summary\n")
            _write(run_root / "deid" / "source" / "export.xml", "DEID_XML\n")

            # Disallowed dirs (must be excluded) containing banned tokens.
            _write(run_root / "staging" / "source" / "export.xml", "John Doe\n")
            _write(run_root / "identity" / "people.json", '{"name":"John Doe"}\n')

            # State registry contains a note with a banned token; snippet must not include notes.
            state_dir = base_out / "state"
            state_dir.mkdir(parents=True, exist_ok=True)
            runs_json = {
                "schema_version": 1,
                "runs": {
                    run_id: {
                        "run_id": run_id,
                        "created_at": "2026-01-21T00:00:00Z",
                        "parent_run_id": None,
                        "input_fingerprint": {"algorithm": "sha256", "sha256": "x", "file_count": 1, "total_bytes": 1},
                        "notes": "John Doe",
                        "artifacts": {
                            "ndjson_dir": f"{run_id}/ndjson",
                            "duckdb_db": f"{run_id}/duckdb/run.duckdb",
                            "reports_dir": f"{run_id}/reports",
                            "note_dir": f"{run_id}/note",
                            "deid_dir": f"{run_id}/deid",
                            "staging_dir": f"{run_id}/staging",
                        },
                    }
                },
            }
            _write(state_dir / "runs.json", json.dumps(runs_json, indent=2, sort_keys=True) + "\n")

            out1 = root / "bundle1.tar.gz"
            out2 = root / "bundle2.tar.gz"

            r1 = subprocess.run(
                [sys.executable, "-m", "healthdelta", "share", "bundle", "--run", str(run_root), "--out", str(out1)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r1.returncode, 0, msg=f"stdout={r1.stdout}\nstderr={r1.stderr}")

            r2 = subprocess.run(
                [sys.executable, "-m", "healthdelta", "share", "bundle", "--run", str(run_root), "--out", str(out2)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r2.returncode, 0, msg=f"stdout={r2.stdout}\nstderr={r2.stderr}")

            b1 = out1.read_bytes()
            b2 = out2.read_bytes()
            self.assertEqual(b1, b2)

            # Banned token from staging/identity/notes must not appear in the archive.
            self.assertNotIn(b"John Doe", b1)

            with tarfile.open(fileobj=io.BytesIO(b1), mode="r:gz") as tf:
                names = tf.getnames()

                self.assertIn(f"{run_id}/ndjson/observations.ndjson", names)
                self.assertIn(f"{run_id}/duckdb/run.duckdb", names)
                self.assertIn(f"{run_id}/reports/summary.json", names)
                self.assertIn(f"{run_id}/note/doctor_note.txt", names)
                self.assertIn(f"{run_id}/deid/source/export.xml", names)
                self.assertIn(f"{run_id}/registry/run_entry.json", names)

                self.assertFalse(any("/staging/" in n or n.startswith(f"{run_id}/staging") for n in names))
                self.assertFalse(any("/identity/" in n or n.startswith(f"{run_id}/identity") for n in names))

                reg = tf.extractfile(f"{run_id}/registry/run_entry.json")
                self.assertIsNotNone(reg)
                reg_obj = json.loads(reg.read().decode("utf-8"))
                self.assertEqual(reg_obj.get("run_id"), run_id)
                self.assertNotIn("notes", reg_obj)


if __name__ == "__main__":
    unittest.main()

