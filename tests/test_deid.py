import json
import tempfile
import unittest
from pathlib import Path
import os


SYNTH_EXPORT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<HealthData>
  <Me name="John Doe" />
</HealthData>
"""

SYNTH_CDA = """<?xml version="1.0" encoding="UTF-8"?>
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

SYNTH_FHIR_PATIENT = {
    "resourceType": "Patient",
    "id": "p1",
    "name": [{"text": "Doe, John"}],
    "birthDate": "1980-01-02",
}

SYNTH_FHIR_OBS = {
    "resourceType": "Observation",
    "id": "o1",
    "subject": {"display": "John Doe"},
}


def _write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class TestDeid(unittest.TestCase):
    def test_deid_removes_names_and_birth_dates(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            # Identity: one person (John Doe) => Patient 1
            identity_dir = root / "data" / "identity"
            people = {
                "people": [
                    {
                        "person_key": "00000000-0000-0000-0000-000000000001",
                        "first_norm": "john",
                        "last_norm": "doe",
                        "created_at": "2026-01-01T00:00:00Z",
                    }
                ]
            }
            _write_json(identity_dir / "people.json", people)

            # Staging run with export.xml + export_cda.xml + 2 clinical jsons
            run_dir = root / "data" / "staging" / "run123"
            export_xml_rel = "source/unpacked/export.xml"
            cda_rel = "source/unpacked/export_cda.xml"
            patient_rel = "clinical-records/patient.json"
            obs_rel = "clinical-records/obs.json"

            (run_dir / "source" / "unpacked").mkdir(parents=True, exist_ok=True)
            (run_dir / export_xml_rel).write_text(SYNTH_EXPORT_XML, encoding="utf-8")
            (run_dir / cda_rel).write_text(SYNTH_CDA, encoding="utf-8")
            _write_json(run_dir / patient_rel, SYNTH_FHIR_PATIENT)
            _write_json(run_dir / obs_rel, SYNTH_FHIR_OBS)

            layout = {"run_id": "run123", "export_xml": export_xml_rel, "clinical_json": [patient_rel, obs_rel]}
            _write_json(run_dir / "layout.json", layout)

            out_dir = root / "data" / "deid" / "run123"

            from healthdelta.deid import deidentify_run

            old_cwd = Path.cwd()
            try:
                import os

                os.chdir(root)
                deidentify_run(staging_run_dir=str(run_dir), identity_dir=str(identity_dir), out_dir=str(out_dir))
            finally:
                os.chdir(old_cwd)

            # mapping.json contains only canonical_person_id -> Patient N
            mapping = json.loads((out_dir / "mapping.json").read_text(encoding="utf-8"))
            self.assertEqual(mapping, {"00000000-0000-0000-0000-000000000001": "Patient 1"})

            # Verify outputs exist
            self.assertTrue((out_dir / "manifest.json").exists())
            self.assertTrue((out_dir / "layout.json").exists())
            self.assertTrue((out_dir / export_xml_rel).exists())
            self.assertTrue((out_dir / cda_rel).exists())
            self.assertTrue((out_dir / patient_rel).exists())
            self.assertTrue((out_dir / obs_rel).exists())

            # Ensure original synthetic name and birth values are gone
            all_text = (out_dir / export_xml_rel).read_text(encoding="utf-8") + (out_dir / cda_rel).read_text(encoding="utf-8")
            all_text += (out_dir / patient_rel).read_text(encoding="utf-8") + (out_dir / obs_rel).read_text(encoding="utf-8")

            self.assertNotIn("John Doe", all_text)
            self.assertNotIn("Doe, John", all_text)
            self.assertNotIn("19800102", all_text)  # CDA birthTime
            self.assertNotIn("1980-01-02", all_text)  # FHIR birthDate

            # Determinism: running again yields identical mapping and identical deid export.xml bytes
            out_dir_2 = root / "data" / "deid" / "run123_2"
            old_cwd2 = Path.cwd()
            try:
                os.chdir(root)
                deidentify_run(staging_run_dir=str(run_dir), identity_dir=str(identity_dir), out_dir=str(out_dir_2))
            finally:
                os.chdir(old_cwd2)

            mapping2 = json.loads((out_dir_2 / "mapping.json").read_text(encoding="utf-8"))
            self.assertEqual(mapping2, mapping)
            self.assertEqual((out_dir_2 / export_xml_rel).read_bytes(), (out_dir / export_xml_rel).read_bytes())


if __name__ == "__main__":
    unittest.main()
