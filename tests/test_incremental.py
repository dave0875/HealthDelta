import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


EXPORT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<HealthData>
  <Record type="HKQuantityTypeIdentifierHeartRate" unit="count/min" value="72" startDate="2020-01-01 00:00:00 -0500" endDate="2020-01-01 00:00:00 -0500"/>
</HealthData>
"""


def _write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class TestIncrementalRuns(unittest.TestCase):
    def test_incremental_pipeline_state_registry_and_noop(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            # Include a banned token in the input directory name to ensure it never leaks into logs/registry.
            input_dir = root / "John Doe export"
            input_dir.mkdir(parents=True, exist_ok=True)
            (input_dir / "export.xml").write_text(EXPORT_XML, encoding="utf-8")

            clinical_dir = input_dir / "clinical-records"
            clinical_dir.mkdir(parents=True, exist_ok=True)
            _write_json(
                clinical_dir / "patient.json",
                {"resourceType": "Patient", "id": "p1", "name": [{"text": "Doe, John"}], "birthDate": "1980-01-02"},
            )

            base_dir = root / "out"
            state_dir = base_dir / "state"

            run1 = subprocess.run(
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
                    "local",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(run1.returncode, 0, msg=f"stdout={run1.stdout}\nstderr={run1.stderr}")
            self.assertNotIn(str(input_dir), run1.stdout)
            self.assertNotIn(str(input_dir), run1.stderr)
            self.assertNotIn("John Doe export", run1.stdout)
            self.assertNotIn("John Doe export", run1.stderr)

            self.assertTrue((state_dir / "runs.json").exists())
            self.assertTrue((state_dir / "LAST_RUN").exists())
            last_1 = (state_dir / "LAST_RUN").read_text(encoding="utf-8").strip()
            self.assertTrue(last_1)

            staging_root = base_dir / "staging"
            run_dirs = [p for p in staging_root.iterdir() if p.is_dir()]
            self.assertEqual(len(run_dirs), 1)
            self.assertEqual(run_dirs[0].name, last_1)

            runs_bytes_1 = (state_dir / "runs.json").read_bytes()
            registry_1 = json.loads(runs_bytes_1.decode("utf-8"))
            self.assertIn("runs", registry_1)
            self.assertIn(last_1, registry_1["runs"])

            entry_1 = registry_1["runs"][last_1]
            self.assertIsNone(entry_1.get("parent_run_id"))
            self.assertEqual(entry_1["run_id"], last_1)
            self.assertIn("input_fingerprint", entry_1)
            self.assertIn("sha256", entry_1["input_fingerprint"])
            self.assertIsInstance(entry_1.get("artifacts", {}).get("staging_dir"), str)
            self.assertTrue(entry_1["artifacts"]["staging_dir"].startswith("staging/"))

            # Second run with identical input: no-op, no new run dirs, no registry mutation.
            run2 = subprocess.run(
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
                    "local",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(run2.returncode, 0, msg=f"stdout={run2.stdout}\nstderr={run2.stderr}")
            self.assertIn("no changes detected", run2.stdout)
            self.assertEqual((state_dir / "runs.json").read_bytes(), runs_bytes_1)
            self.assertEqual((state_dir / "LAST_RUN").read_text(encoding="utf-8").strip(), last_1)
            run_dirs_2 = [p for p in staging_root.iterdir() if p.is_dir()]
            self.assertEqual(len(run_dirs_2), 1)

            # Change input (new file): should create new run and link parent.
            _write_json(clinical_dir / "obs.json", {"resourceType": "Observation", "id": "o1"})
            run3 = subprocess.run(
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
                    "local",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(run3.returncode, 0, msg=f"stdout={run3.stdout}\nstderr={run3.stderr}")
            last_3 = (state_dir / "LAST_RUN").read_text(encoding="utf-8").strip()
            self.assertNotEqual(last_3, last_1)

            registry_3 = json.loads((state_dir / "runs.json").read_text(encoding="utf-8"))
            entry_3 = registry_3["runs"][last_3]
            self.assertEqual(entry_3["parent_run_id"], last_1)

            # Ensure the registry does not leak the input directory name.
            runs_json_text = (state_dir / "runs.json").read_text(encoding="utf-8")
            self.assertNotIn(str(input_dir), runs_json_text)
            self.assertNotIn("John Doe export", runs_json_text)

    def test_run_register_is_idempotent_and_updates_last_run(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_dir = root / "export_dir"
            input_dir.mkdir(parents=True, exist_ok=True)
            (input_dir / "export.xml").write_text(EXPORT_XML, encoding="utf-8")

            base_dir = root / "out"
            run = subprocess.run(
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
                    "local",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(run.returncode, 0, msg=f"stdout={run.stdout}\nstderr={run.stderr}")

            staging_root = base_dir / "staging"
            run_dirs = [p for p in staging_root.iterdir() if p.is_dir()]
            self.assertEqual(len(run_dirs), 1)
            run_dir = run_dirs[0]

            state_dir = base_dir / "state_register"
            reg1 = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "healthdelta",
                    "run",
                    "register",
                    "--run",
                    str(run_dir),
                    "--state",
                    str(state_dir),
                    "--note",
                    "test",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(reg1.returncode, 0, msg=f"stdout={reg1.stdout}\nstderr={reg1.stderr}")
            self.assertEqual((state_dir / "LAST_RUN").read_text(encoding="utf-8").strip(), run_dir.name)
            runs_bytes_1 = (state_dir / "runs.json").read_bytes()

            # Register again: no changes (byte-stable).
            reg2 = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "healthdelta",
                    "run",
                    "register",
                    "--run",
                    str(run_dir),
                    "--state",
                    str(state_dir),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(reg2.returncode, 0, msg=f"stdout={reg2.stdout}\nstderr={reg2.stderr}")
            self.assertEqual((state_dir / "runs.json").read_bytes(), runs_bytes_1)


if __name__ == "__main__":
    unittest.main()

