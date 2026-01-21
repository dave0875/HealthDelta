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


EXPORT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<HealthData>
  <Me name="John Doe" />
  <Record type="HKQuantityTypeIdentifierHeartRate" unit="count/min" value="72" startDate="2020-01-01 00:00:00 -0500" endDate="2020-01-01 00:00:00 -0500"/>
</HealthData>
"""


EXPORT_CDA = """<?xml version="1.0" encoding="UTF-8"?>
<ClinicalDocument xmlns="urn:hl7-org:v3">
  <recordTarget>
    <patientRole>
      <patient>
        <name>
          <given>John</given>
          <family>Doe</family>
        </name>
        <birthTime value="19800102"/>
      </patient>
    </patientRole>
  </recordTarget>
  <component>
    <structuredBody>
      <component>
        <section>
          <entry>
            <observation classCode="OBS" moodCode="EVN">
              <effectiveTime value="20200101112233"/>
              <code code="8867-4" displayName="Heart rate"/>
              <value xsi:type="PQ" value="72" unit="/min" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"/>
            </observation>
          </entry>
        </section>
      </component>
    </structuredBody>
  </component>
</ClinicalDocument>
"""


def _write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _stdout_kv(stdout: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in stdout.splitlines():
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k.strip():
            out[k.strip()] = v.strip()
    return out


class TestOperatorAll(unittest.TestCase):
    @unittest.skipUnless(_duckdb_available(), "duckdb not installed in this environment")
    def test_run_all_share_mode_creates_artifacts_and_is_noop_when_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            # Include banned tokens in input directory name to ensure it never leaks into logs/registry.
            input_dir = root / "John Doe export"
            input_dir.mkdir(parents=True, exist_ok=True)

            (input_dir / "export.xml").write_text(EXPORT_XML, encoding="utf-8")
            (input_dir / "export_cda.xml").write_text(EXPORT_CDA, encoding="utf-8")

            clinical_dir = input_dir / "clinical-records"
            clinical_dir.mkdir(parents=True, exist_ok=True)
            _write_json(
                clinical_dir / "patient.json",
                {"resourceType": "Patient", "id": "p1", "name": [{"text": "Doe, John"}], "birthDate": "1980-01-02"},
            )
            _write_json(
                clinical_dir / "obs.json",
                {
                    "resourceType": "Observation",
                    "id": "o1",
                    "subject": {"reference": "Patient/p1"},
                    "effectiveDateTime": "2020-01-01T01:02:03Z",
                    "valueQuantity": {"value": 72, "unit": "count/min"},
                },
            )
            _write_json(
                clinical_dir / "doc.json",
                {
                    "resourceType": "DocumentReference",
                    "id": "d1",
                    "status": "current",
                    "subject": {"reference": "Patient/p1"},
                    "date": "2020-01-02T03:04:05Z",
                },
            )

            base_out = root / "out"

            run1 = subprocess.run(
                [sys.executable, "-m", "healthdelta", "run", "all", "--input", str(input_dir), "--out", str(base_out)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(run1.returncode, 0, msg=f"stdout={run1.stdout}\nstderr={run1.stderr}")
            self.assertNotIn(str(input_dir), run1.stdout)
            self.assertNotIn(str(input_dir), run1.stderr)
            self.assertNotIn("John Doe export", run1.stdout)
            self.assertNotIn("John Doe export", run1.stderr)

            kv1 = _stdout_kv(run1.stdout)
            self.assertEqual(kv1.get("status"), "created")
            run_id = kv1.get("run_id")
            self.assertIsInstance(run_id, str)
            self.assertTrue(run_id)

            run_root = base_out / run_id
            expected = {
                "staging": run_root / "staging",
                "identity": run_root / "identity",
                "deid": run_root / "deid",
                "ndjson": run_root / "ndjson",
                "duckdb": run_root / "duckdb" / "run.duckdb",
                "reports": run_root / "reports",
                "note": run_root / "note",
                "note_txt": run_root / "note" / "doctor_note.txt",
                "note_md": run_root / "note" / "doctor_note.md",
            }
            self.assertTrue(expected["staging"].is_dir())
            self.assertTrue(expected["identity"].is_dir())
            self.assertTrue(expected["deid"].is_dir())
            self.assertTrue(expected["ndjson"].is_dir())
            self.assertTrue(expected["duckdb"].is_file())
            self.assertTrue(expected["reports"].is_dir())
            self.assertTrue(expected["note"].is_dir())
            self.assertTrue(expected["note_txt"].is_file())
            self.assertTrue(expected["note_md"].is_file())

            ndjson_files = [
                expected["ndjson"] / "observations.ndjson",
                expected["ndjson"] / "documents.ndjson",
            ]
            for p in ndjson_files:
                self.assertTrue(p.exists(), msg=f"missing {p}")

            reports_files = [
                expected["reports"] / "summary.json",
                expected["reports"] / "summary.md",
                expected["reports"] / "coverage_by_person.csv",
                expected["reports"] / "coverage_by_source.csv",
                expected["reports"] / "timeline_daily_counts.csv",
            ]
            for p in reports_files:
                self.assertTrue(p.exists(), msg=f"missing {p}")

            note_files = [expected["note_txt"], expected["note_md"]]
            for p in note_files:
                self.assertTrue(p.exists(), msg=f"missing {p}")
                self.assertTrue(p.read_bytes().endswith(b"\n"), msg=f"not newline-terminated: {p}")

            # Save bytes for no-op verification.
            runs_bytes_1 = (base_out / "state" / "runs.json").read_bytes()
            last_1 = (base_out / "state" / "LAST_RUN").read_text(encoding="utf-8").strip()
            self.assertEqual(last_1, run_id)
            summary_json_1 = (expected["reports"] / "summary.json").read_bytes()
            summary_md_1 = (expected["reports"] / "summary.md").read_bytes()
            note_txt_1 = expected["note_txt"].read_bytes()
            note_md_1 = expected["note_md"].read_bytes()

            # Share-safe: outputs must not contain synthetic name or DOB tokens.
            combined = ""
            for p in [*ndjson_files, *reports_files, *note_files, base_out / "state" / "runs.json"]:
                combined += p.read_text(encoding="utf-8", errors="replace")
            for banned in ["John Doe", "Doe, John", "1980-01-02", "19800102", "John Doe export"]:
                self.assertNotIn(banned, combined)

            # Registry pointers include note paths.
            registry = json.loads(runs_bytes_1.decode("utf-8"))
            entry = registry.get("runs", {}).get(run_id, {})
            artifacts = entry.get("artifacts", {}) if isinstance(entry, dict) else {}
            self.assertEqual(artifacts.get("note_dir"), f"{run_id}/note")
            self.assertEqual(artifacts.get("doctor_note_txt"), f"{run_id}/note/doctor_note.txt")
            self.assertEqual(artifacts.get("doctor_note_md"), f"{run_id}/note/doctor_note.md")

            # Second run: no-op, no new run directory, no file changes.
            run2 = subprocess.run(
                [sys.executable, "-m", "healthdelta", "run", "all", "--input", str(input_dir), "--out", str(base_out)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(run2.returncode, 0, msg=f"stdout={run2.stdout}\nstderr={run2.stderr}")
            kv2 = _stdout_kv(run2.stdout)
            self.assertEqual(kv2.get("status"), "no_changes")
            self.assertEqual(kv2.get("run_id"), run_id)

            run_dirs = [p for p in base_out.iterdir() if p.is_dir() and p.name != "state"]
            self.assertEqual(run_dirs, [run_root])

            self.assertEqual((base_out / "state" / "runs.json").read_bytes(), runs_bytes_1)
            self.assertEqual((base_out / "state" / "LAST_RUN").read_text(encoding="utf-8").strip(), last_1)
            self.assertEqual((expected["reports"] / "summary.json").read_bytes(), summary_json_1)
            self.assertEqual((expected["reports"] / "summary.md").read_bytes(), summary_md_1)
            self.assertEqual(expected["note_txt"].read_bytes(), note_txt_1)
            self.assertEqual(expected["note_md"].read_bytes(), note_md_1)


if __name__ == "__main__":
    unittest.main()
