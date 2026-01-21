import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def _duckdb_available() -> bool:
    try:
        import duckdb  # noqa: F401

        return True
    except Exception:
        return False


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _ndjson_line(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n"


class TestDoctorNote(unittest.TestCase):
    @unittest.skipUnless(_duckdb_available(), "duckdb not installed in this environment")
    def test_note_build_is_deterministic_and_share_safe(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ndjson_dir = root / "ndjson"
            ndjson_dir.mkdir(parents=True, exist_ok=True)

            # Minimal synthetic NDJSON (derived from Issue #8 schema expectations).
            run_id = "run123"
            _write_text(
                ndjson_dir / "observations.ndjson",
                _ndjson_line(
                    {
                        "canonical_person_id": "p1",
                        "source": "healthkit",
                        "source_file": "source/export.xml",
                        "event_time": "2020-01-01T00:00:00Z",
                        "run_id": run_id,
                        "hk_type": "HKQuantityTypeIdentifierHeartRate",
                        "value": "72",
                        "unit": "count/min",
                        "event_key": "k1",
                    }
                )
                + _ndjson_line(
                    {
                        "canonical_person_id": "p1",
                        "source": "cda",
                        "source_file": "source/unpacked/export_cda.xml",
                        "event_time": "2020-01-02T00:00:00Z",
                        "run_id": run_id,
                        "code": "8867-4",
                        "value": "72",
                        "unit": "/min",
                        "event_key": "k2",
                    }
                ),
            )
            _write_text(
                ndjson_dir / "documents.ndjson",
                _ndjson_line(
                    {
                        "canonical_person_id": "p1",
                        "source": "fhir",
                        "source_file": "clinical/clinical-records/doc.json",
                        "event_time": "2020-01-03T00:00:00Z",
                        "run_id": run_id,
                        "resource_type": "DocumentReference",
                        "status": "current",
                        "event_key": "d1",
                    }
                ),
            )

            db_path = root / "out.duckdb"
            out_dir = root / "note"

            build = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "healthdelta",
                    "duckdb",
                    "build",
                    "--input",
                    str(ndjson_dir),
                    "--db",
                    str(db_path),
                    "--replace",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(build.returncode, 0, msg=f"stdout={build.stdout}\nstderr={build.stderr}")

            note1 = subprocess.run(
                [sys.executable, "-m", "healthdelta", "note", "build", "--db", str(db_path), "--out", str(out_dir), "--mode", "share"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(note1.returncode, 0, msg=f"stdout={note1.stdout}\nstderr={note1.stderr}")

            txt = out_dir / "doctor_note.txt"
            md = out_dir / "doctor_note.md"
            self.assertTrue(txt.exists())
            self.assertTrue(md.exists())
            self.assertTrue(txt.read_bytes().endswith(b"\n"))
            self.assertTrue(md.read_bytes().endswith(b"\n"))

            expected = (
                "HealthDelta Summary\n"
                "run_id=run123\n"
                "generated_at=2020-01-03T00:00:00Z\n"
                "people=1\n"
                "event_time_range=2020-01-01T00:00:00Z..2020-01-03T00:00:00Z\n"
                "totals.observations=2\n"
                "totals.documents=1\n"
                "totals.medications=0\n"
                "totals.conditions=0\n"
                "sources.healthkit=1\n"
                "sources.fhir=1\n"
                "sources.cda=1\n"
                "signals.top_observations=HKQuantityTypeIdentifierHeartRate:1;8867-4:1\n"
                "No names, dates of birth, or identifying text included.\n"
            ).encode("utf-8")
            self.assertEqual(txt.read_bytes(), expected)
            self.assertEqual(md.read_bytes(), expected)

            # Share-safe / deterministic rerun.
            banned = ["John Doe", "Doe, John", "1980-01-02", "19800102"]
            combined = txt.read_text(encoding="utf-8") + md.read_text(encoding="utf-8")
            for b in banned:
                self.assertNotIn(b, combined)

            before_txt = txt.read_bytes()
            before_md = md.read_bytes()
            note2 = subprocess.run(
                [sys.executable, "-m", "healthdelta", "note", "build", "--db", str(db_path), "--out", str(out_dir), "--mode", "share"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(note2.returncode, 0, msg=f"stdout={note2.stdout}\nstderr={note2.stderr}")
            self.assertEqual(txt.read_bytes(), before_txt)
            self.assertEqual(md.read_bytes(), before_md)


if __name__ == "__main__":
    unittest.main()

