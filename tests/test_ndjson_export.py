import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


HEALTHKIT_EXPORT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<HealthData>
  <Me name="John Doe" />
  <Record type="HKQuantityTypeIdentifierHeartRate" unit="count/min" value="72" startDate="2020-01-01 00:00:00 -0500" endDate="2020-01-01 00:00:00 -0500"/>
</HealthData>
"""


FHIR_PATIENT = {"resourceType": "Patient", "id": "p1", "name": [{"text": "Doe, John"}], "birthDate": "1980-01-02"}
FHIR_OBS = {
    "resourceType": "Observation",
    "id": "o1",
    "status": "final",
    "subject": {"reference": "Patient/p1"},
    "effectiveDateTime": "2020-01-01T01:02:03Z",
    "code": {"text": "Heart rate"},
    "valueQuantity": {"value": 72, "unit": "count/min"},
}
FHIR_DOC = {
    "resourceType": "DocumentReference",
    "id": "d1",
    "status": "current",
    "subject": {"reference": "Patient/p1"},
    "date": "2020-01-02T03:04:05Z",
    "type": {"text": "Discharge summary"},
}
FHIR_MED = {
    "resourceType": "MedicationRequest",
    "id": "m1",
    "status": "active",
    "subject": {"reference": "Patient/p1"},
    "authoredOn": "2020-01-03T00:00:00Z",
}
FHIR_COND = {
    "resourceType": "Condition",
    "id": "c1",
    "subject": {"reference": "Patient/p1"},
    "recordedDate": "2020-01-04T00:00:00Z",
    "code": {"text": "Hypertension"},
}


EXPORT_CDA_XML = """<?xml version="1.0" encoding="UTF-8"?>
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


def _read_ndjson(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[dict] = []
    for line in lines:
        if not line.strip():
            continue
        out.append(json.loads(line))
    return out


class TestNdjsonExport(unittest.TestCase):
    def test_export_ndjson_local_and_share_are_deterministic_and_pii_free(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_dir = root / "export_dir"
            input_dir.mkdir(parents=True, exist_ok=True)

            (input_dir / "export.xml").write_text(HEALTHKIT_EXPORT_XML, encoding="utf-8")
            (input_dir / "export_cda.xml").write_text(EXPORT_CDA_XML, encoding="utf-8")

            clinical_dir = input_dir / "clinical-records"
            clinical_dir.mkdir(parents=True, exist_ok=True)

            _write_json(clinical_dir / "patient.json", FHIR_PATIENT)
            _write_json(clinical_dir / "obs.json", FHIR_OBS)
            _write_json(clinical_dir / "doc.json", FHIR_DOC)
            _write_json(clinical_dir / "med.json", FHIR_MED)
            _write_json(clinical_dir / "cond.json", FHIR_COND)

            base_dir = root / "out"

            pipe = subprocess.run(
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
            self.assertEqual(pipe.returncode, 0, msg=f"stdout={pipe.stdout}\nstderr={pipe.stderr}")

            staging_root = base_dir / "staging"
            run_dirs = [p for p in staging_root.iterdir() if p.is_dir()]
            self.assertEqual(len(run_dirs), 1)
            run_dir = run_dirs[0]
            deid_dir = base_dir / "deid" / run_dir.name
            self.assertTrue(deid_dir.exists())

            out_local = root / "ndjson_local"
            exp1 = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "healthdelta",
                    "export",
                    "ndjson",
                    "--input",
                    str(run_dir),
                    "--out",
                    str(out_local),
                    "--mode",
                    "local",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(exp1.returncode, 0, msg=f"stdout={exp1.stdout}\nstderr={exp1.stderr}")

            expected_files = [
                out_local / "observations.ndjson",
                out_local / "documents.ndjson",
                out_local / "medications.ndjson",
                out_local / "conditions.ndjson",
            ]
            for p in expected_files:
                self.assertTrue(p.exists(), msg=f"missing {p}")
                self.assertTrue(p.read_bytes().endswith(b"\n"), msg=f"not newline-terminated: {p}")

            observations = _read_ndjson(out_local / "observations.ndjson")
            documents = _read_ndjson(out_local / "documents.ndjson")
            meds = _read_ndjson(out_local / "medications.ndjson")
            conds = _read_ndjson(out_local / "conditions.ndjson")

            # HealthKit Record (1) + FHIR Observation (1) + CDA observation-like entry (1)
            self.assertEqual(len(observations), 3)
            self.assertEqual(len(documents), 1)
            self.assertEqual(len(meds), 1)
            self.assertEqual(len(conds), 1)

            combined = "".join(p.read_text(encoding="utf-8") for p in expected_files)
            self.assertNotIn("John Doe", combined)
            self.assertNotIn("Doe, John", combined)
            self.assertNotIn("1980-01-02", combined)
            self.assertNotIn("19800102", combined)

            for row in [*observations, *documents, *meds, *conds]:
                self.assertIn("canonical_person_id", row)
                self.assertIn("source", row)
                self.assertIn("source_file", row)
                self.assertIn("event_time", row)
                self.assertIn("run_id", row)
                self.assertIsInstance(row["canonical_person_id"], str)
                self.assertIn(row["source"], ["healthkit", "fhir", "cda"])
                self.assertIsInstance(row["source_file"], str)

            before_bytes = {p.name: p.read_bytes() for p in expected_files}

            # Determinism: second run produces byte-identical NDJSON
            exp2 = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "healthdelta",
                    "export",
                    "ndjson",
                    "--input",
                    str(run_dir),
                    "--out",
                    str(out_local),
                    "--mode",
                    "local",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(exp2.returncode, 0, msg=f"stdout={exp2.stdout}\nstderr={exp2.stderr}")

            for p in expected_files:
                self.assertEqual(p.read_bytes(), before_bytes[p.name])

            # Share mode: reads deid outputs
            out_share = root / "ndjson_share"
            exp_share = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "healthdelta",
                    "export",
                    "ndjson",
                    "--input",
                    str(deid_dir),
                    "--out",
                    str(out_share),
                    "--mode",
                    "share",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(exp_share.returncode, 0, msg=f"stdout={exp_share.stdout}\nstderr={exp_share.stderr}")
            self.assertTrue((out_share / "observations.ndjson").exists())


if __name__ == "__main__":
    unittest.main()
