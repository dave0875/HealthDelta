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
FHIR_MED_STATEMENT = {
    "resourceType": "MedicationStatement",
    "id": "ms1",
    "status": "active",
    "subject": {"reference": "Patient/p1"},
    "effectiveDateTime": "2020-01-03T06:00:00Z",
}
FHIR_MED_DISPENSE = {
    "resourceType": "MedicationDispense",
    "id": "md1",
    "status": "completed",
    "subject": {"reference": "Patient/p1"},
    "whenHandedOver": "2020-01-03T12:00:00Z",
}
FHIR_COND = {
    "resourceType": "Condition",
    "id": "c1",
    "subject": {"reference": "Patient/p1"},
    "recordedDate": "2020-01-04T00:00:00Z",
    "code": {"text": "Hypertension"},
}
FHIR_ALLERGY = {
    "resourceType": "AllergyIntolerance",
    "id": "a1",
    "subject": {"reference": "Patient/p1"},
    "onsetDateTime": "2020-01-04T07:00:00Z",
    "code": {"text": "Peanut allergy"},
}
FHIR_IMMUNIZATION = {
    "resourceType": "Immunization",
    "id": "i1",
    "status": "completed",
    "patient": {"reference": "Patient/p1"},
    "occurrenceDateTime": "2020-01-08T09:00:00Z",
    "vaccineCode": {"text": "Influenza"},
}
FHIR_ENCOUNTER = {
    "resourceType": "Encounter",
    "id": "e1",
    "status": "finished",
    "subject": {"reference": "Patient/p1"},
    "period": {"start": "2020-01-05T10:00:00Z", "end": "2020-01-05T12:00:00Z"},
}
FHIR_PROC = {
    "resourceType": "Procedure",
    "id": "pr1",
    "status": "completed",
    "subject": {"reference": "Patient/p1"},
    "performedPeriod": {"start": "2020-01-06T09:30:00Z", "end": "2020-01-06T10:00:00Z"},
    "code": {"text": "Procedure A"},
}
FHIR_DIAG_REPORT = {
    "resourceType": "DiagnosticReport",
    "id": "dr1",
    "status": "final",
    "subject": {"reference": "Patient/p1"},
    "issued": "2020-01-07T08:00:00Z",
    "result": [{"reference": "Observation/o1"}],
    "code": {"text": "Basic metabolic panel"},
}
FHIR_DIAG_REPORT_MISSING = {
    "resourceType": "DiagnosticReport",
    "id": "dr2",
    "status": "final",
    "subject": {"reference": "Patient/p1"},
    "issued": "2020-01-07T09:00:00Z",
    "result": [{"reference": "Observation/missing"}],
    "code": {"text": "Missing results"},
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

EXPORT_CDA_DISCHARGE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<ClinicalDocument xmlns="urn:hl7-org:v3">
  <componentOf>
    <encompassingEncounter>
      <effectiveTime>
        <low value="20200110120000"/>
        <high value="20200111103000"/>
      </effectiveTime>
    </encompassingEncounter>
  </componentOf>
  <component>
    <structuredBody>
      <component>
        <section>
          <code code="11450-4" displayName="Problem List"/>
          <title>Problem List</title>
          <entry>
            <observation classCode="OBS" moodCode="EVN">
              <effectiveTime value="20200110130000"/>
              <code code="75326-9" displayName="Problem"/>
              <value xsi:type="ST" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" value="Hypertension"/>
            </observation>
          </entry>
        </section>
      </component>
      <component>
        <section>
          <code code="18842-5" displayName="Discharge Summary"/>
          <title>Discharge Summary</title>
          <entry>
            <observation classCode="OBS" moodCode="EVN">
              <effectiveTime value="20200111100000"/>
              <code code="34109-9" displayName="Discharge diagnosis"/>
              <value xsi:type="ST" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" value="Recovered"/>
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
    def test_export_ndjson_cda_discharge_sections_and_encounter_rows(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            run_dir = root / "staging" / "run-cda"
            cda_rel = "source/unpacked/export_cda.xml"
            (run_dir / "source" / "unpacked").mkdir(parents=True, exist_ok=True)
            (run_dir / cda_rel).write_text(EXPORT_CDA_DISCHARGE_XML, encoding="utf-8")

            _write_json(
                run_dir / "layout.json",
                {
                    "run_id": "run-cda",
                    "export_cda_xml": cda_rel,
                    "clinical_json": [],
                },
            )

            out_local = root / "ndjson_local"
            run = subprocess.run(
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
            self.assertEqual(run.returncode, 0, msg=f"stdout={run.stdout}\nstderr={run.stderr}")

            observations = _read_ndjson(out_local / "observations.ndjson")
            encounters = _read_ndjson(out_local / "encounters.ndjson")

            section_rows = [r for r in observations if r.get("resource_type") == "CDASection"]
            self.assertEqual(len(section_rows), 2)
            self.assertEqual({r.get("section_code") for r in section_rows}, {"11450-4", "18842-5"})

            observation_rows = [r for r in observations if r.get("resource_type") == "CDAObservation"]
            self.assertGreaterEqual(len(observation_rows), 2)

            encounter_rows = [r for r in encounters if r.get("resource_type") == "CDAEncounter"]
            self.assertEqual(len(encounter_rows), 1)
            self.assertEqual(encounter_rows[0].get("event_time"), "2020-01-10T12:00:00Z")

    def test_export_ndjson_resolves_subject_and_patient_identifier_mappings(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            base = root / "out"
            run_dir = base / "staging" / "run-1"
            clinical_dir = run_dir / "source" / "clinical-records"
            clinical_dir.mkdir(parents=True, exist_ok=True)

            layout = {
                "run_id": "run-1",
                "clinical_json": [
                    "source/clinical-records/obs_subject_identifier.json",
                    "source/clinical-records/obs_reference_fallback.json",
                    "source/clinical-records/obs_ambiguous.json",
                    "source/clinical-records/immunization_patient_identifier.json",
                ],
            }
            _write_json(run_dir / "layout.json", layout)

            _write_json(
                clinical_dir / "obs_subject_identifier.json",
                {
                    "resourceType": "Observation",
                    "id": "o-subject",
                    "status": "final",
                    "subject": {"identifier": {"system": "urn:mrn", "value": "111"}},
                    "effectiveDateTime": "2020-01-01T00:00:00Z",
                },
            )
            _write_json(
                clinical_dir / "obs_reference_fallback.json",
                {
                    "resourceType": "Observation",
                    "id": "o-fallback",
                    "status": "final",
                    "subject": {
                        "reference": "Patient/p1",
                        "identifier": {"system": "urn:mrn", "value": "unmapped"},
                    },
                    "effectiveDateTime": "2020-01-01T01:00:00Z",
                },
            )
            _write_json(
                clinical_dir / "obs_ambiguous.json",
                {
                    "resourceType": "Observation",
                    "id": "o-ambiguous",
                    "status": "final",
                    "subject": {
                        "reference": "Patient/p1",
                        "identifier": {"system": "urn:mrn", "value": "222"},
                    },
                    "effectiveDateTime": "2020-01-01T02:00:00Z",
                },
            )
            _write_json(
                clinical_dir / "immunization_patient_identifier.json",
                {
                    "resourceType": "Immunization",
                    "id": "i-subject",
                    "status": "completed",
                    "patient": {"identifier": {"system": "urn:mrn", "value": "111"}},
                    "occurrenceDateTime": "2020-01-01T03:00:00Z",
                },
            )

            identity = base / "identity"
            identity.mkdir(parents=True, exist_ok=True)
            _write_json(
                identity / "people.json",
                {
                    "people": [
                        {"person_key": "person-a"},
                        {"person_key": "person-b"},
                    ]
                },
            )
            _write_json(
                identity / "aliases.json",
                {
                    "aliases": [
                        {
                            "person_key": "person-a",
                            "source": {
                                "external_ids": [
                                    {"system": "fhir:id", "value": "p1"},
                                    {"system": "urn:mrn", "value": "111"},
                                ]
                            },
                        },
                        {
                            "person_key": "person-b",
                            "source": {
                                "external_ids": [
                                    {"system": "urn:mrn", "value": "222"},
                                ]
                            },
                        },
                    ]
                },
            )

            out_local = root / "ndjson_local"
            run = subprocess.run(
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
            self.assertEqual(run.returncode, 0, msg=f"stdout={run.stdout}\nstderr={run.stderr}")

            observations = _read_ndjson(out_local / "observations.ndjson")
            by_source_id = {r.get("source_id"): r for r in observations if isinstance(r, dict)}
            self.assertEqual(by_source_id["Observation/o-subject"]["canonical_person_id"], "person-a")
            self.assertEqual(by_source_id["Observation/o-fallback"]["canonical_person_id"], "person-a")
            self.assertEqual(by_source_id["Observation/o-ambiguous"]["canonical_person_id"], "unresolved")
            self.assertEqual(by_source_id["Immunization/i-subject"]["canonical_person_id"], "person-a")
            for row in by_source_id.values():
                self.assertIsInstance(row.get("source_system"), str)
                self.assertTrue(row.get("source_system", "").startswith("ss_"))
                self.assertEqual(len(row.get("source_system", "")), 15)
                self.assertNotIn("urn:mrn", row.get("source_system", ""))

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
            _write_json(clinical_dir / "med_statement.json", FHIR_MED_STATEMENT)
            _write_json(clinical_dir / "med_dispense.json", FHIR_MED_DISPENSE)
            _write_json(clinical_dir / "cond.json", FHIR_COND)
            _write_json(clinical_dir / "allergy.json", FHIR_ALLERGY)
            _write_json(clinical_dir / "immunization.json", FHIR_IMMUNIZATION)
            _write_json(clinical_dir / "encounter.json", FHIR_ENCOUNTER)
            _write_json(clinical_dir / "procedure.json", FHIR_PROC)
            _write_json(clinical_dir / "diag_report.json", FHIR_DIAG_REPORT)
            _write_json(clinical_dir / "diag_report_missing.json", FHIR_DIAG_REPORT_MISSING)

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
                out_local / "encounters.ndjson",
                out_local / "procedures.ndjson",
                out_local / "diagnostic_reports.ndjson",
            ]
            for p in expected_files:
                self.assertTrue(p.exists(), msg=f"missing {p}")
                self.assertTrue(p.read_bytes().endswith(b"\n"), msg=f"not newline-terminated: {p}")

            observations = _read_ndjson(out_local / "observations.ndjson")
            documents = _read_ndjson(out_local / "documents.ndjson")
            meds = _read_ndjson(out_local / "medications.ndjson")
            conds = _read_ndjson(out_local / "conditions.ndjson")
            encounters = _read_ndjson(out_local / "encounters.ndjson")
            procedures = _read_ndjson(out_local / "procedures.ndjson")
            reports = _read_ndjson(out_local / "diagnostic_reports.ndjson")

            # HealthKit Record (1) + FHIR Observation (1) + CDA observation-like entry (1) + Immunization (1)
            self.assertEqual(len(observations), 4)
            self.assertEqual(len(documents), 1)
            self.assertEqual(len(meds), 3)
            self.assertEqual(len(conds), 2)
            self.assertEqual(len(encounters), 1)
            self.assertEqual(len(procedures), 1)
            self.assertEqual(len(reports), 2)

            self.assertEqual(encounters[0].get("resource_type"), "Encounter")
            self.assertEqual(encounters[0].get("event_time"), "2020-01-05T10:00:00Z")

            self.assertEqual(procedures[0].get("resource_type"), "Procedure")
            self.assertEqual(procedures[0].get("event_time"), "2020-01-06T09:30:00Z")

            allergy_rows = [c for c in conds if c.get("resource_type") == "AllergyIntolerance"]
            self.assertEqual(len(allergy_rows), 1)
            self.assertEqual(allergy_rows[0].get("event_time"), "2020-01-04T07:00:00Z")

            imm_rows = [o for o in observations if o.get("resource_type") == "Immunization"]
            self.assertEqual(len(imm_rows), 1)
            self.assertEqual(imm_rows[0].get("event_time"), "2020-01-08T09:00:00Z")

            report_by_id = {r.get("source_id"): r for r in reports}
            self.assertIn("DiagnosticReport/dr1", report_by_id)
            self.assertIn("DiagnosticReport/dr2", report_by_id)

            fhir_obs = [o for o in observations if o.get("resource_type") == "Observation" and o.get("source") == "fhir"]
            self.assertTrue(fhir_obs)
            obs_key = fhir_obs[0].get("record_key")
            self.assertIn(obs_key, report_by_id["DiagnosticReport/dr1"].get("result_observation_record_keys", []))
            self.assertNotIn("result_observation_record_keys", report_by_id["DiagnosticReport/dr2"])
            med_types = {m.get("resource_type") for m in meds}
            self.assertEqual(
                med_types,
                {"MedicationRequest", "MedicationStatement", "MedicationDispense"},
            )

            combined = "".join(p.read_text(encoding="utf-8") for p in expected_files)
            self.assertNotIn("John Doe", combined)
            self.assertNotIn("Doe, John", combined)
            self.assertNotIn("1980-01-02", combined)
            self.assertNotIn("19800102", combined)

            for row in [*observations, *documents, *meds, *conds, *encounters, *procedures, *reports]:
                self.assertIn("schema_version", row)
                self.assertIn("canonical_person_id", row)
                self.assertIn("source", row)
                self.assertIn("source_system", row)
                self.assertIn("source_file", row)
                self.assertIn("event_time", row)
                self.assertIn("run_id", row)
                self.assertIn("record_key", row)
                self.assertIsInstance(row["canonical_person_id"], str)
                self.assertIn(row["source"], ["healthkit", "fhir", "cda"])
                self.assertTrue(row["source_system"].startswith("ss_"))
                self.assertIsInstance(row["source_file"], str)
                self.assertIsInstance(row["schema_version"], int)
                self.assertIsInstance(row["record_key"], str)

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
