import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


EXPORT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<HealthData>
  <Me name="John Doe" />
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
</ClinicalDocument>
"""


def _write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class TestPipeline(unittest.TestCase):
    def test_pipeline_share_mode_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_dir = root / "export_dir"
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
                {"resourceType": "Observation", "id": "o1", "subject": {"display": "John Doe"}},
            )

            base_dir = root / "out"

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "healthdelta",
                    "pipeline",
                    "run",
                    "--input",
                    str(input_dir),
                    "--out",
                    str(base_dir),
                    "--mode",
                    "share",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, msg=f"stdout={result.stdout}\nstderr={result.stderr}")

            staging_root = base_dir / "staging"
            run_dirs = [p for p in staging_root.iterdir() if p.is_dir()]
            self.assertEqual(len(run_dirs), 1)
            run_dir = run_dirs[0]

            self.assertTrue((run_dir / "manifest.json").exists())
            self.assertTrue((run_dir / "layout.json").exists())
            self.assertTrue((run_dir / "run_report.json").exists())

            report = json.loads((run_dir / "run_report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["mode"], "share")
            self.assertTrue(report["stages"]["deid"]["executed"])

            deid_dir = base_dir / "deid" / run_dir.name
            self.assertTrue((deid_dir / "mapping.json").exists())
            self.assertTrue((deid_dir / "manifest.json").exists())
            self.assertTrue((deid_dir / "layout.json").exists())

            # De-id should not contain original name or DOB
            combined = ""
            for p in [
                deid_dir / "source" / "unpacked" / "export_cda.xml",
                deid_dir / "source" / "export.xml",
                deid_dir / "source" / "clinical" / "clinical-records" / "patient.json",
                deid_dir / "source" / "clinical" / "clinical-records" / "obs.json",
            ]:
                self.assertTrue(p.exists(), msg=f"missing {p}")
                combined += p.read_text(encoding="utf-8")

            self.assertNotIn("John Doe", combined)
            self.assertNotIn("Doe, John", combined)
            self.assertNotIn("19800102", combined)
            self.assertNotIn("1980-01-02", combined)

            # Rerun should be idempotent and not error
            result2 = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "healthdelta",
                    "pipeline",
                    "run",
                    "--input",
                    str(input_dir),
                    "--out",
                    str(base_dir),
                    "--mode",
                    "share",
                    "--run-id",
                    run_dir.name,
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result2.returncode, 0, msg=f"stdout={result2.stdout}\nstderr={result2.stderr}")


if __name__ == "__main__":
    unittest.main()

