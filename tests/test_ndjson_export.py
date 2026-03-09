import json
import shutil
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
    "effectivePeriod": {"start": "2020-01-01T01:02:03Z", "end": "2020-01-01T01:07:03Z"},
    "encounter": {"reference": "Encounter/e1"},
    "code": {
        "coding": [{"system": "http://loinc.org", "code": "8867-4", "display": "Heart rate"}],
        "text": "Heart rate",
    },
    "valueQuantity": {"value": 72, "unit": "count/min"},
    "component": [
        {
            "code": {
                "coding": [{"system": "http://loinc.org", "code": "8480-6", "display": "Systolic blood pressure"}],
                "text": "Systolic blood pressure",
            },
            "valueQuantity": {"value": 120, "unit": "mm[Hg]"},
        },
        {
            "code": {
                "coding": [{"system": "http://loinc.org", "code": "8462-4", "display": "Diastolic blood pressure"}],
                "text": "Diastolic blood pressure",
            },
            "valueQuantity": {"value": 80, "unit": "mm[Hg]"},
        },
    ],
}
FHIR_DOC = {
    "resourceType": "DocumentReference",
    "id": "d1",
    "status": "current",
    "subject": {"reference": "Patient/p1"},
    "date": "2020-01-02T03:04:05Z",
    "type": {
        "coding": [{"system": "http://loinc.org", "code": "18842-5", "display": "Discharge summary"}],
        "text": "Discharge summary",
    },
    "content": [
        {
            "attachment": {
                "contentType": "application/pdf",
                "title": "Discharge Summary PDF",
                "size": 12345,
                "hash": "YWJjMTIz",
                "data": "VGhpcyBzaG91bGQgbm90IGJlIGV4cG9ydGVk",
                "url": "Binary/bin1",
            }
        }
    ],
}
FHIR_BINARY = {
    "resourceType": "Binary",
    "id": "bin1",
    "contentType": "application/pdf",
    "securityContext": {"reference": "DocumentReference/d1"},
    "data": "aGVsbG8gd29ybGQ=",
}
FHIR_MED = {
    "resourceType": "MedicationRequest",
    "id": "m1",
    "status": "active",
    "subject": {"reference": "Patient/p1"},
    "authoredOn": "2020-01-03T00:00:00Z",
    "medicationCodeableConcept": {
        "coding": [{"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": "860975", "display": "metformin 500 MG"}],
        "text": "Metformin",
    },
}
FHIR_MED_STATEMENT = {
    "resourceType": "MedicationStatement",
    "id": "ms1",
    "status": "active",
    "subject": {"reference": "Patient/p1"},
    "effectiveDateTime": "2020-01-03T06:00:00Z",
    "medicationCodeableConcept": {
        "coding": [{"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": "617314", "display": "aspirin 81 MG"}],
        "text": "Aspirin",
    },
}
FHIR_MED_MISSING = {
    "resourceType": "MedicationStatement",
    "id": "ms2",
    "subject": {"reference": "Patient/p1"},
}
FHIR_MED_DISPENSE = {
    "resourceType": "MedicationDispense",
    "id": "md1",
    "status": "completed",
    "subject": {"reference": "Patient/p1"},
    "whenHandedOver": "2020-01-03T12:00:00Z",
    "medicationCodeableConcept": {
        "coding": [{"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": "1049502", "display": "insulin glargine"}],
        "text": "Insulin glargine",
    },
}
FHIR_COND = {
    "resourceType": "Condition",
    "id": "c1",
    "subject": {"reference": "Patient/p1"},
    "recordedDate": "2020-01-04T00:00:00Z",
    "onsetDateTime": "2019-12-31T00:00:00Z",
    "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active"}]},
    "verificationStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-ver-status", "code": "confirmed"}]},
    "code": {
        "coding": [{"system": "http://snomed.info/sct", "code": "38341003", "display": "Hypertensive disorder"}],
        "text": "Hypertension",
    },
}
FHIR_COND_MISSING = {
    "resourceType": "Condition",
    "id": "c2",
    "subject": {"reference": "Patient/p1"},
}
FHIR_ALLERGY = {
    "resourceType": "AllergyIntolerance",
    "id": "a1",
    "subject": {"reference": "Patient/p1"},
    "onsetDateTime": "2020-01-04T07:00:00Z",
    "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical", "code": "active"}]},
    "code": {
        "coding": [{"system": "http://snomed.info/sct", "code": "91935009", "display": "Allergy to peanuts"}],
        "text": "Peanut allergy",
    },
}
FHIR_ALLERGY_MISSING = {
    "resourceType": "AllergyIntolerance",
    "id": "a2",
    "subject": {"reference": "Patient/p1"},
}
FHIR_IMMUNIZATION = {
    "resourceType": "Immunization",
    "id": "i1",
    "status": "completed",
    "patient": {"reference": "Patient/p1"},
    "occurrenceDateTime": "2020-01-08T09:00:00Z",
    "vaccineCode": {
        "coding": [{"system": "http://hl7.org/fhir/sid/cvx", "code": "140", "display": "Influenza, seasonal, injectable"}],
        "text": "Influenza",
    },
}
FHIR_IMMUNIZATION_MISSING = {
    "resourceType": "Immunization",
    "id": "i2",
    "patient": {"reference": "Patient/p1"},
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
    "code": {
        "coding": [{"system": "http://snomed.info/sct", "code": "80146002", "display": "Appendectomy"}],
        "text": "Procedure A",
    },
}
FHIR_PROC_MISSING = {
    "resourceType": "Procedure",
    "id": "pr2",
    "subject": {"reference": "Patient/p1"},
}
FHIR_DIAG_REPORT = {
    "resourceType": "DiagnosticReport",
    "id": "dr1",
    "status": "final",
    "subject": {"reference": "Patient/p1"},
    "effectivePeriod": {"start": "2020-01-07T07:30:00Z", "end": "2020-01-07T08:00:00Z"},
    "issued": "2020-01-07T08:05:00Z",
    "result": [{"reference": "Observation/o1"}],
    "code": {
        "coding": [{"system": "http://loinc.org", "code": "24323-8", "display": "Basic metabolic 2000 panel - Serum or Plasma"}],
        "text": "Basic metabolic panel",
    },
    "presentedForm": [
        {
            "contentType": "application/pdf",
            "title": "Lab report attachment",
            "size": 11,
            "url": "Binary/bin1",
        }
    ],
}
FHIR_DIAG_REPORT_MISSING = {
    "resourceType": "DiagnosticReport",
    "id": "dr2",
    "subject": {"reference": "Patient/p1"},
    "issued": "2020-01-07T09:00:00Z",
    "result": [{"reference": "Observation/missing"}],
    "code": {"text": "Missing results"},
}
FHIR_GOAL = {
    "resourceType": "Goal",
    "id": "g1",
    "lifecycleStatus": "active",
    "subject": {"reference": "Patient/p1"},
    "startDate": "2020-01-09",
    "target": [{"dueDate": "2020-03-01"}],
    "description": {"text": "Lower blood pressure"},
}
FHIR_CAREPLAN = {
    "resourceType": "CarePlan",
    "id": "cp1",
    "status": "active",
    "intent": "plan",
    "subject": {"reference": "Patient/p1"},
    "period": {"start": "2020-01-10T00:00:00Z", "end": "2020-02-10T00:00:00Z"},
    "goal": [{"reference": "Goal/g1"}],
    "title": "Hypertension management",
}
FHIR_SERVICE_REQUEST = {
    "resourceType": "ServiceRequest",
    "id": "sr1",
    "status": "active",
    "intent": "order",
    "subject": {"reference": "Patient/p1"},
    "authoredOn": "2020-01-11T00:00:00Z",
    "code": {
        "coding": [{"system": "http://snomed.info/sct", "code": "306206005", "display": "Referral to cardiology service"}],
        "text": "Cardiology referral",
    },
    "performer": [{"reference": "Organization/org1"}, {"reference": "Practitioner/prac1"}],
}
FHIR_COVERAGE = {
    "resourceType": "Coverage",
    "id": "cv1",
    "status": "active",
    "beneficiary": {"reference": "Patient/p1"},
    "type": {
        "coding": [{"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "EHCPOL", "display": "extended healthcare"}]
    },
    "relationship": {
        "coding": [{"system": "http://terminology.hl7.org/CodeSystem/subscriber-relationship", "code": "self", "display": "Self"}]
    },
    "period": {"start": "2020-01-12T00:00:00Z", "end": "2021-01-12T00:00:00Z"},
    "payor": [{"reference": "Organization/org1"}],
}
FHIR_ORGANIZATION = {
    "resourceType": "Organization",
    "id": "org1",
    "name": "Example Hospital",
    "type": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/organization-type", "code": "prov", "display": "Healthcare Provider"}]}],
    "address": [{"city": "Boston", "state": "MA", "postalCode": "02110"}],
}
FHIR_PRACTITIONER = {
    "resourceType": "Practitioner",
    "id": "prac1",
    "name": [{"text": "Dr. Avery Stone"}],
    "identifier": [{"system": "http://hl7.org/fhir/sid/us-npi", "value": "9999999999"}],
}
FHIR_LOCATION = {
    "resourceType": "Location",
    "id": "loc1",
    "name": "North Wing Clinic",
    "address": {"city": "Cambridge", "state": "MA", "postalCode": "02139"},
}
FHIR_PROVENANCE = {
    "resourceType": "Provenance",
    "id": "prov1",
    "recorded": "2020-01-12T12:30:00Z",
    "agent": [{"who": {"reference": "Practitioner/prac1"}}],
    "target": [{"reference": "Observation/o1"}, {"reference": "DocumentReference/d1"}],
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
    def test_export_ndjson_uses_clinical_records_fixture_pack(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            run_dir = root / "staging" / "run-fixture-pack"
            clinical_dir = run_dir / "source" / "clinical-records"
            fixture_dir = Path(__file__).resolve().parent / "fixtures" / "clinical_records_v1"
            shutil.copytree(fixture_dir, clinical_dir)

            _write_json(
                run_dir / "layout.json",
                {
                    "run_id": "run-fixture-pack",
                    "clinical_json": sorted(str(path.relative_to(run_dir)).replace("\\", "/") for path in clinical_dir.glob("*.json")),
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

            documents = _read_ndjson(out_local / "documents.ndjson")
            binaries = _read_ndjson(out_local / "binaries.ndjson")
            observations = _read_ndjson(out_local / "observations.ndjson")
            provenance_rows = _read_ndjson(out_local / "provenance.ndjson")

            self.assertEqual(len(documents), 1)
            self.assertEqual(len(binaries), 1)
            self.assertEqual(len(observations), 1)
            self.assertEqual(len(provenance_rows), 1)
            self.assertEqual(documents[0]["attachments"][0]["binary_id"], "bin-fixture")
            self.assertEqual(binaries[0]["security_context_reference"], "DocumentReference/doc-fixture")
            self.assertEqual(provenance_rows[0]["target_references"], ["DocumentReference/doc-fixture", "Observation/obs-fixture"])

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
            _write_json(clinical_dir / "binary.json", FHIR_BINARY)
            _write_json(clinical_dir / "med.json", FHIR_MED)
            _write_json(clinical_dir / "med_statement.json", FHIR_MED_STATEMENT)
            _write_json(clinical_dir / "med_statement_missing.json", FHIR_MED_MISSING)
            _write_json(clinical_dir / "med_dispense.json", FHIR_MED_DISPENSE)
            _write_json(clinical_dir / "cond.json", FHIR_COND)
            _write_json(clinical_dir / "cond_missing.json", FHIR_COND_MISSING)
            _write_json(clinical_dir / "allergy.json", FHIR_ALLERGY)
            _write_json(clinical_dir / "allergy_missing.json", FHIR_ALLERGY_MISSING)
            _write_json(clinical_dir / "immunization.json", FHIR_IMMUNIZATION)
            _write_json(clinical_dir / "immunization_missing.json", FHIR_IMMUNIZATION_MISSING)
            _write_json(clinical_dir / "encounter.json", FHIR_ENCOUNTER)
            _write_json(clinical_dir / "procedure.json", FHIR_PROC)
            _write_json(clinical_dir / "procedure_missing.json", FHIR_PROC_MISSING)
            _write_json(clinical_dir / "diag_report.json", FHIR_DIAG_REPORT)
            _write_json(clinical_dir / "diag_report_missing.json", FHIR_DIAG_REPORT_MISSING)
            _write_json(clinical_dir / "goal.json", FHIR_GOAL)
            _write_json(clinical_dir / "careplan.json", FHIR_CAREPLAN)
            _write_json(clinical_dir / "service_request.json", FHIR_SERVICE_REQUEST)
            _write_json(clinical_dir / "coverage.json", FHIR_COVERAGE)
            _write_json(clinical_dir / "organization.json", FHIR_ORGANIZATION)
            _write_json(clinical_dir / "practitioner.json", FHIR_PRACTITIONER)
            _write_json(clinical_dir / "location.json", FHIR_LOCATION)
            _write_json(clinical_dir / "provenance.json", FHIR_PROVENANCE)

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
                out_local / "binaries.ndjson",
                out_local / "medications.ndjson",
                out_local / "conditions.ndjson",
                out_local / "encounters.ndjson",
                out_local / "procedures.ndjson",
                out_local / "diagnostic_reports.ndjson",
                out_local / "goals.ndjson",
                out_local / "careplans.ndjson",
                out_local / "service_requests.ndjson",
                out_local / "coverages.ndjson",
                out_local / "organizations.ndjson",
                out_local / "practitioners.ndjson",
                out_local / "locations.ndjson",
                out_local / "provenance.ndjson",
            ]
            for p in expected_files:
                self.assertTrue(p.exists(), msg=f"missing {p}")
                self.assertTrue(p.read_bytes().endswith(b"\n"), msg=f"not newline-terminated: {p}")

            observations = _read_ndjson(out_local / "observations.ndjson")
            documents = _read_ndjson(out_local / "documents.ndjson")
            binaries = _read_ndjson(out_local / "binaries.ndjson")
            meds = _read_ndjson(out_local / "medications.ndjson")
            conds = _read_ndjson(out_local / "conditions.ndjson")
            encounters = _read_ndjson(out_local / "encounters.ndjson")
            procedures = _read_ndjson(out_local / "procedures.ndjson")
            reports = _read_ndjson(out_local / "diagnostic_reports.ndjson")
            goals = _read_ndjson(out_local / "goals.ndjson")
            careplans = _read_ndjson(out_local / "careplans.ndjson")
            service_requests = _read_ndjson(out_local / "service_requests.ndjson")
            coverages = _read_ndjson(out_local / "coverages.ndjson")
            organizations = _read_ndjson(out_local / "organizations.ndjson")
            practitioners = _read_ndjson(out_local / "practitioners.ndjson")
            locations = _read_ndjson(out_local / "locations.ndjson")
            provenance_rows = _read_ndjson(out_local / "provenance.ndjson")

            # HealthKit Record (1) + FHIR Observation (1) + CDA observation-like entry (1) + Immunization (2)
            self.assertEqual(len(observations), 5)
            self.assertEqual(len(documents), 1)
            self.assertEqual(len(binaries), 1)
            self.assertEqual(len(meds), 4)
            self.assertEqual(len(conds), 4)
            self.assertEqual(len(encounters), 1)
            self.assertEqual(len(procedures), 2)
            self.assertEqual(len(reports), 2)
            self.assertEqual(len(goals), 1)
            self.assertEqual(len(careplans), 1)
            self.assertEqual(len(service_requests), 1)
            self.assertEqual(len(coverages), 1)
            self.assertEqual(len(organizations), 1)
            self.assertEqual(len(practitioners), 1)
            self.assertEqual(len(locations), 1)
            self.assertEqual(len(provenance_rows), 1)

            self.assertEqual(encounters[0].get("resource_type"), "Encounter")
            self.assertEqual(encounters[0].get("event_time"), "2020-01-05T10:00:00Z")
            self.assertEqual(encounters[0].get("record_id"), "e1")
            self.assertEqual(encounters[0].get("record_type"), "Encounter")
            self.assertEqual(encounters[0].get("encounter_id"), "e1")
            self.assertEqual(encounters[0].get("subject_reference"), "Patient/p1")
            self.assertEqual(encounters[0].get("period_start"), "2020-01-05T10:00:00Z")
            self.assertEqual(encounters[0].get("period_end"), "2020-01-05T12:00:00Z")

            self.assertEqual(documents[0].get("record_id"), "d1")
            self.assertEqual(documents[0].get("record_type"), "DocumentReference")
            self.assertEqual(documents[0].get("document_reference_id"), "d1")
            self.assertEqual(documents[0].get("subject_reference"), "Patient/p1")
            self.assertEqual(documents[0].get("type_system"), "http://loinc.org")
            self.assertEqual(documents[0].get("type_code"), "18842-5")
            self.assertEqual(documents[0].get("display"), "Discharge summary")
            self.assertEqual(
                documents[0].get("attachments"),
                [
                    {
                        "content_type": "application/pdf",
                        "binary_id": "bin1",
                        "hash": "YWJjMTIz",
                        "size": 12345,
                        "title": "Discharge Summary PDF",
                    }
                ],
            )
            self.assertNotIn("data", json.dumps(documents[0], sort_keys=True))
            self.assertNotIn("url", json.dumps(documents[0], sort_keys=True))

            self.assertEqual(binaries[0].get("record_id"), "bin1")
            self.assertEqual(binaries[0].get("record_type"), "Binary")
            self.assertEqual(binaries[0].get("binary_id"), "bin1")
            self.assertEqual(binaries[0].get("content_type"), "application/pdf")
            self.assertEqual(binaries[0].get("content_size_bytes"), 11)
            self.assertEqual(binaries[0].get("security_context_reference"), "DocumentReference/d1")
            self.assertTrue(binaries[0].get("data_present"))
            self.assertNotIn('"data":', json.dumps(binaries[0], sort_keys=True))

            self.assertEqual(goals[0].get("record_id"), "g1")
            self.assertEqual(goals[0].get("record_type"), "Goal")
            self.assertEqual(goals[0].get("goal_id"), "g1")
            self.assertEqual(goals[0].get("subject_reference"), "Patient/p1")
            self.assertEqual(goals[0].get("status"), "active")
            self.assertEqual(goals[0].get("start_date"), "2020-01-09")
            self.assertEqual(goals[0].get("target_due_date"), "2020-03-01")
            self.assertEqual(goals[0].get("description"), "Lower blood pressure")

            self.assertEqual(careplans[0].get("record_id"), "cp1")
            self.assertEqual(careplans[0].get("record_type"), "CarePlan")
            self.assertEqual(careplans[0].get("careplan_id"), "cp1")
            self.assertEqual(careplans[0].get("subject_reference"), "Patient/p1")
            self.assertEqual(careplans[0].get("status"), "active")
            self.assertEqual(careplans[0].get("intent"), "plan")
            self.assertEqual(careplans[0].get("period_start"), "2020-01-10T00:00:00Z")
            self.assertEqual(careplans[0].get("period_end"), "2020-02-10T00:00:00Z")
            self.assertEqual(careplans[0].get("goal_ids"), ["g1"])
            self.assertEqual(careplans[0].get("title"), "Hypertension management")

            self.assertEqual(service_requests[0].get("record_id"), "sr1")
            self.assertEqual(service_requests[0].get("record_type"), "ServiceRequest")
            self.assertEqual(service_requests[0].get("service_request_id"), "sr1")
            self.assertEqual(service_requests[0].get("subject_reference"), "Patient/p1")
            self.assertEqual(service_requests[0].get("status"), "active")
            self.assertEqual(service_requests[0].get("intent"), "order")
            self.assertEqual(service_requests[0].get("authored_on"), "2020-01-11T00:00:00Z")
            self.assertEqual(service_requests[0].get("code_system"), "http://snomed.info/sct")
            self.assertEqual(service_requests[0].get("code"), "306206005")
            self.assertEqual(service_requests[0].get("display"), "Referral to cardiology service")
            self.assertEqual(service_requests[0].get("performer_references"), ["Organization/org1", "Practitioner/prac1"])

            self.assertEqual(coverages[0].get("record_id"), "cv1")
            self.assertEqual(coverages[0].get("record_type"), "Coverage")
            self.assertEqual(coverages[0].get("coverage_id"), "cv1")
            self.assertEqual(coverages[0].get("subject_reference"), "Patient/p1")
            self.assertEqual(coverages[0].get("status"), "active")
            self.assertEqual(coverages[0].get("type_system"), "http://terminology.hl7.org/CodeSystem/v3-ActCode")
            self.assertEqual(coverages[0].get("type_code"), "EHCPOL")
            self.assertEqual(coverages[0].get("subscriber_relationship"), "self")
            self.assertEqual(coverages[0].get("period_start"), "2020-01-12T00:00:00Z")
            self.assertEqual(coverages[0].get("period_end"), "2021-01-12T00:00:00Z")
            self.assertEqual(coverages[0].get("payor_references"), ["Organization/org1"])

            self.assertEqual(organizations[0].get("record_id"), "org1")
            self.assertEqual(organizations[0].get("record_type"), "Organization")
            self.assertEqual(organizations[0].get("organization_id"), "org1")
            self.assertEqual(organizations[0].get("name"), "Example Hospital")
            self.assertEqual(organizations[0].get("type_system"), "http://terminology.hl7.org/CodeSystem/organization-type")
            self.assertEqual(organizations[0].get("type_code"), "prov")
            self.assertEqual(organizations[0].get("address_city"), "Boston")
            self.assertEqual(organizations[0].get("address_state"), "MA")
            self.assertEqual(organizations[0].get("address_postal_code"), "02110")

            self.assertEqual(practitioners[0].get("record_id"), "prac1")
            self.assertEqual(practitioners[0].get("record_type"), "Practitioner")
            self.assertEqual(practitioners[0].get("practitioner_id"), "prac1")
            self.assertEqual(practitioners[0].get("name"), "Dr. Avery Stone")
            self.assertEqual(practitioners[0].get("identifier_system"), "http://hl7.org/fhir/sid/us-npi")
            self.assertEqual(practitioners[0].get("identifier_value"), "9999999999")

            self.assertEqual(locations[0].get("record_id"), "loc1")
            self.assertEqual(locations[0].get("record_type"), "Location")
            self.assertEqual(locations[0].get("location_id"), "loc1")
            self.assertEqual(locations[0].get("name"), "North Wing Clinic")
            self.assertEqual(locations[0].get("address_city"), "Cambridge")
            self.assertEqual(locations[0].get("address_state"), "MA")
            self.assertEqual(locations[0].get("address_postal_code"), "02139")

            self.assertEqual(provenance_rows[0].get("record_id"), "prov1")
            self.assertEqual(provenance_rows[0].get("record_type"), "Provenance")
            self.assertEqual(provenance_rows[0].get("provenance_id"), "prov1")
            self.assertEqual(provenance_rows[0].get("recorded"), "2020-01-12T12:30:00Z")
            self.assertEqual(provenance_rows[0].get("agent_references"), ["Practitioner/prac1"])
            self.assertEqual(
                provenance_rows[0].get("target_references"),
                ["DocumentReference/d1", "Observation/o1"],
            )
            self.assertEqual(len(provenance_rows[0].get("target_record_keys", [])), 2)

            proc_by_id = {p.get("source_id"): p for p in procedures}
            self.assertEqual(proc_by_id["Procedure/pr1"].get("resource_type"), "Procedure")
            self.assertEqual(proc_by_id["Procedure/pr1"].get("event_time"), "2020-01-06T09:30:00Z")
            self.assertEqual(proc_by_id["Procedure/pr1"].get("code_system"), "http://snomed.info/sct")
            self.assertEqual(proc_by_id["Procedure/pr1"].get("code"), "80146002")
            self.assertEqual(proc_by_id["Procedure/pr1"].get("display"), "Appendectomy")
            self.assertEqual(proc_by_id["Procedure/pr1"].get("status"), "completed")
            self.assertIsNone(proc_by_id["Procedure/pr2"].get("code_system"))
            self.assertIsNone(proc_by_id["Procedure/pr2"].get("code"))
            self.assertIsNone(proc_by_id["Procedure/pr2"].get("display"))
            self.assertIsNone(proc_by_id["Procedure/pr2"].get("status"))
            self.assertIn("warnings.procedure_missing.code=1", exp1.stderr)
            self.assertIn("warnings.procedure_missing.status=1", exp1.stderr)

            allergy_rows = [c for c in conds if c.get("resource_type") == "AllergyIntolerance"]
            self.assertEqual(len(allergy_rows), 2)
            allergy_by_id = {c.get("source_id"): c for c in allergy_rows}
            self.assertEqual(allergy_by_id["AllergyIntolerance/a1"].get("event_time"), "2020-01-04T07:00:00Z")
            condition_rows = [c for c in conds if c.get("resource_type") == "Condition"]
            self.assertEqual(len(condition_rows), 2)
            cond_by_id = {c.get("source_id"): c for c in condition_rows}
            self.assertEqual(cond_by_id["Condition/c1"].get("code_system"), "http://snomed.info/sct")
            self.assertEqual(cond_by_id["Condition/c1"].get("code"), "38341003")
            self.assertEqual(cond_by_id["Condition/c1"].get("display"), "Hypertensive disorder")
            self.assertEqual(cond_by_id["Condition/c1"].get("clinical_status"), "active")
            self.assertEqual(cond_by_id["Condition/c1"].get("verification_status"), "confirmed")
            self.assertEqual(cond_by_id["Condition/c1"].get("onset_time"), "2019-12-31T00:00:00Z")
            self.assertIsNone(cond_by_id["Condition/c2"].get("code_system"))
            self.assertIsNone(cond_by_id["Condition/c2"].get("code"))
            self.assertIsNone(cond_by_id["Condition/c2"].get("display"))
            self.assertIsNone(cond_by_id["Condition/c2"].get("clinical_status"))
            self.assertIsNone(cond_by_id["Condition/c2"].get("verification_status"))
            self.assertIsNone(cond_by_id["Condition/c2"].get("onset_time"))
            self.assertIn("warnings.condition_missing.code=1", exp1.stderr)
            self.assertIn("warnings.condition_missing.clinical_status=1", exp1.stderr)
            self.assertIn("warnings.condition_missing.verification_status=1", exp1.stderr)

            med_by_id = {m.get("source_id"): m for m in meds}
            self.assertEqual(med_by_id["MedicationRequest/m1"].get("code_system"), "http://www.nlm.nih.gov/research/umls/rxnorm")
            self.assertEqual(med_by_id["MedicationRequest/m1"].get("code"), "860975")
            self.assertEqual(med_by_id["MedicationRequest/m1"].get("display"), "metformin 500 MG")
            self.assertEqual(med_by_id["MedicationRequest/m1"].get("status"), "active")
            self.assertIsNone(med_by_id["MedicationStatement/ms2"].get("code_system"))
            self.assertIsNone(med_by_id["MedicationStatement/ms2"].get("code"))
            self.assertIsNone(med_by_id["MedicationStatement/ms2"].get("display"))
            self.assertIsNone(med_by_id["MedicationStatement/ms2"].get("status"))
            self.assertIn("warnings.medication_missing.code=1", exp1.stderr)
            self.assertIn("warnings.medication_missing.status=1", exp1.stderr)

            self.assertEqual(allergy_by_id["AllergyIntolerance/a1"].get("code_system"), "http://snomed.info/sct")
            self.assertEqual(allergy_by_id["AllergyIntolerance/a1"].get("code"), "91935009")
            self.assertEqual(allergy_by_id["AllergyIntolerance/a1"].get("display"), "Allergy to peanuts")
            self.assertEqual(allergy_by_id["AllergyIntolerance/a1"].get("status"), "active")
            self.assertIsNone(allergy_by_id["AllergyIntolerance/a2"].get("code_system"))
            self.assertIsNone(allergy_by_id["AllergyIntolerance/a2"].get("code"))
            self.assertIsNone(allergy_by_id["AllergyIntolerance/a2"].get("display"))
            self.assertIsNone(allergy_by_id["AllergyIntolerance/a2"].get("status"))
            self.assertIn("warnings.allergy_missing.code=1", exp1.stderr)
            self.assertIn("warnings.allergy_missing.status=1", exp1.stderr)

            imm_rows = [o for o in observations if o.get("resource_type") == "Immunization"]
            self.assertEqual(len(imm_rows), 2)
            imm_by_id = {o.get("source_id"): o for o in imm_rows}
            self.assertEqual(imm_by_id["Immunization/i1"].get("event_time"), "2020-01-08T09:00:00Z")
            self.assertEqual(imm_by_id["Immunization/i1"].get("code_system"), "http://hl7.org/fhir/sid/cvx")
            self.assertEqual(imm_by_id["Immunization/i1"].get("code"), "140")
            self.assertEqual(imm_by_id["Immunization/i1"].get("display"), "Influenza, seasonal, injectable")
            self.assertEqual(imm_by_id["Immunization/i1"].get("status"), "completed")
            self.assertIsNone(imm_by_id["Immunization/i2"].get("code_system"))
            self.assertIsNone(imm_by_id["Immunization/i2"].get("code"))
            self.assertIsNone(imm_by_id["Immunization/i2"].get("display"))
            self.assertIsNone(imm_by_id["Immunization/i2"].get("status"))
            self.assertIn("warnings.immunization_missing.code=1", exp1.stderr)
            self.assertIn("warnings.immunization_missing.status=1", exp1.stderr)

            report_by_id = {r.get("source_id"): r for r in reports}
            self.assertIn("DiagnosticReport/dr1", report_by_id)
            self.assertIn("DiagnosticReport/dr2", report_by_id)
            self.assertEqual(report_by_id["DiagnosticReport/dr1"].get("record_id"), "dr1")
            self.assertEqual(report_by_id["DiagnosticReport/dr1"].get("record_type"), "DiagnosticReport")
            self.assertEqual(report_by_id["DiagnosticReport/dr1"].get("diagnostic_report_id"), "dr1")
            self.assertEqual(report_by_id["DiagnosticReport/dr1"].get("subject_reference"), "Patient/p1")
            self.assertEqual(report_by_id["DiagnosticReport/dr1"].get("effective_start"), "2020-01-07T07:30:00Z")
            self.assertEqual(report_by_id["DiagnosticReport/dr1"].get("effective_end"), "2020-01-07T08:00:00Z")
            self.assertEqual(report_by_id["DiagnosticReport/dr1"].get("code_system"), "http://loinc.org")
            self.assertEqual(report_by_id["DiagnosticReport/dr1"].get("code"), "24323-8")
            self.assertEqual(
                report_by_id["DiagnosticReport/dr1"].get("display"),
                "Basic metabolic 2000 panel - Serum or Plasma",
            )
            self.assertEqual(report_by_id["DiagnosticReport/dr1"].get("status"), "final")
            self.assertEqual(
                report_by_id["DiagnosticReport/dr1"].get("presented_forms"),
                [
                    {
                        "binary_id": "bin1",
                        "content_type": "application/pdf",
                        "size": 11,
                        "title": "Lab report attachment",
                    }
                ],
            )
            self.assertIsNone(report_by_id["DiagnosticReport/dr2"].get("status"))

            fhir_obs = [o for o in observations if o.get("resource_type") == "Observation" and o.get("source") == "fhir"]
            self.assertTrue(fhir_obs)
            self.assertEqual(fhir_obs[0].get("record_id"), "o1")
            self.assertEqual(fhir_obs[0].get("record_type"), "Observation")
            self.assertEqual(fhir_obs[0].get("observation_id"), "o1")
            self.assertEqual(fhir_obs[0].get("code_system"), "http://loinc.org")
            self.assertEqual(fhir_obs[0].get("code"), "8867-4")
            self.assertEqual(fhir_obs[0].get("value"), 72)
            self.assertEqual(fhir_obs[0].get("unit"), "count/min")
            self.assertEqual(fhir_obs[0].get("effective_start"), "2020-01-01T01:02:03Z")
            self.assertEqual(fhir_obs[0].get("effective_end"), "2020-01-01T01:07:03Z")
            self.assertEqual(fhir_obs[0].get("subject_reference"), "Patient/p1")
            self.assertEqual(fhir_obs[0].get("encounter_id"), "e1")
            self.assertEqual(
                fhir_obs[0].get("components"),
                [
                    {
                        "code": "8462-4",
                        "code_system": "http://loinc.org",
                        "display": "Diastolic blood pressure",
                        "unit": "mm[Hg]",
                        "value": 80,
                    },
                    {
                        "code": "8480-6",
                        "code_system": "http://loinc.org",
                        "display": "Systolic blood pressure",
                        "unit": "mm[Hg]",
                        "value": 120,
                    },
                ],
            )
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

            for row in [*observations, *documents, *binaries, *meds, *conds, *encounters, *procedures, *reports, *goals, *careplans, *service_requests, *coverages, *organizations, *practitioners, *locations, *provenance_rows]:
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
