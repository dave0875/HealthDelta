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
                "HealthDelta Doctor's Note\n"
                "run_id=run123\n"
                "generated_at=2020-01-03T00:00:00Z\n"
                "\n"
                "Summary\n"
                "- Scope covers 1 person from 2020-01-01T00:00:00Z to 2020-01-03T00:00:00Z across 3 active days.\n"
                "- Current data is mixed: fitness/wellness observations and structured clinical records are both present.\n"
                "- Most common observed signals: Heart rate (1 row); 8867-4 (1 row).\n"
                "- Clinical record coverage includes documents (1 row).\n"
                "- Source mix includes healthkit (1 row), fhir (1 row), cda (1 row).\n"
                "- Share-safe note: no names, dates of birth, identifiers, or free-text clinical narratives are included.\n"
                "\n"
                "Facts\n"
                "people=1\n"
                "active_days=3\n"
                "event_time_range=2020-01-01T00:00:00Z..2020-01-03T00:00:00Z\n"
                "domain_mix=mixed\n"
                "totals.observations=2\n"
                "totals.documents=1\n"
                "totals.medications=0\n"
                "totals.conditions=0\n"
                "totals.encounters=0\n"
                "totals.procedures=0\n"
                "totals.diagnostic_reports=0\n"
                "sources.healthkit=1\n"
                "sources.fhir=1\n"
                "sources.cda=1\n"
                "signals.top_observations=HKQuantityTypeIdentifierHeartRate:1;8867-4:1\n"
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

    @unittest.skipUnless(_duckdb_available(), "duckdb not installed in this environment")
    def test_note_surfaces_recent_clinical_happenings_when_labeled_fhir_observations_exist(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ndjson_dir = root / "ndjson"
            ndjson_dir.mkdir(parents=True, exist_ok=True)

            run_id = "run-clinical"
            recent_rows: list[str] = []
            labels = [
                ("2026-02-24T09:00:00Z", "SpO2", "%", 96),
                ("2026-02-24T10:00:00Z", "SpO2", "%", 97),
                ("2026-02-24T11:00:00Z", "SpO2", "%", 98),
                ("2026-02-09T09:00:00Z", "Hemoglobin [Mass/volume] in Blood", "g/dL", 10.1),
                ("2026-02-09T10:00:00Z", "Hemoglobin [Mass/volume] in Blood", "g/dL", 9.8),
                ("2026-02-09T11:00:00Z", "Leukocytes [#/volume] in Blood by Automated count", "K/UL", 3.2),
                ("2026-02-27T08:00:00Z", "Glucose [Mass/volume] in Serum or Plasma", "mg/dL", 141),
                ("2026-02-27T09:00:00Z", "Creatinine [Mass/volume] in Serum or Plasma", "mg/dL", 1.4),
                ("2026-02-27T10:00:00Z", "Sodium [Moles/volume] in Serum or Plasma", "mmol/L", 135),
                ("2026-03-06T08:00:00Z", "Crossmatch Result", None, None),
                ("2026-03-06T09:00:00Z", "ABO and Rh group [Type] in Blood", None, None),
                ("2026-03-06T10:00:00Z", "Blood group antibody screen [Presence] in Serum or Plasma", None, None),
            ]
            for idx, (event_time, display, unit, value_num) in enumerate(labels, start=1):
                obj = {
                    "canonical_person_id": "p-clinical",
                    "source": "fhir",
                    "source_file": f"clinical/clinical-records/obs-{idx}.json",
                    "event_time": event_time,
                    "run_id": run_id,
                    "record_key": f"rk{idx}",
                    "event_key": f"ek{idx}",
                    "display": display,
                }
                if unit is not None:
                    obj["unit"] = unit
                if value_num is not None:
                    obj["value_num"] = value_num
                recent_rows.append(_ndjson_line(obj))

            _write_text(ndjson_dir / "observations.ndjson", "".join(recent_rows))
            _write_text(ndjson_dir / "documents.ndjson", "")

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

            note = subprocess.run(
                [sys.executable, "-m", "healthdelta", "note", "build", "--db", str(db_path), "--out", str(out_dir), "--mode", "share"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(note.returncode, 0, msg=f"stdout={note.stdout}\nstderr={note.stderr}")

            rendered = (out_dir / "doctor_note.md").read_text(encoding="utf-8")
            self.assertIn("Recent clinical activity spans 1 share-safe patient bucket", rendered)
            self.assertIn("Recent clinical themes included", rendered)
            self.assertIn("oxygenation monitoring", rendered)
            self.assertIn("blood counts and differentials", rendered)
            self.assertIn("serum chemistries", rendered)
            self.assertIn("blood-bank and transfusion workflow", rendered)
            self.assertIn("Highest recent clinical activity occurred on 2026-02-09 (3 rows), 2026-02-24 (3 rows), 2026-02-27 (3 rows).", rendered)
            self.assertIn("recent_clinical.top_themes=", rendered)


if __name__ == "__main__":
    unittest.main()
