import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class TestNdjsonValidate(unittest.TestCase):
    def test_schema_files_exist_for_all_streams(self) -> None:
        root = Path(__file__).resolve().parents[1] / "schemas" / "ndjson" / "v2"
        expected = {
            "observations.schema.json",
            "documents.schema.json",
            "medications.schema.json",
            "conditions.schema.json",
            "encounters.schema.json",
            "procedures.schema.json",
            "diagnostic_reports.schema.json",
            "goals.schema.json",
            "careplans.schema.json",
            "service_requests.schema.json",
            "coverages.schema.json",
            "organizations.schema.json",
            "practitioners.schema.json",
            "locations.schema.json",
            "provenance.schema.json",
        }
        self.assertTrue(root.exists(), msg=f"missing schema dir: {root}")
        got = {p.name for p in root.glob("*.schema.json")}
        self.assertTrue(expected.issubset(got), msg=f"missing schema files: {sorted(expected - got)}")

    def test_validate_ok(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            nd = root / "ndjson"
            nd.mkdir(parents=True, exist_ok=True)

            _write(
                nd / "observations.ndjson",
                '{"schema_version":2,"record_key":"k1","canonical_person_id":"p1","source":"healthkit","source_file":"source/export.xml","event_time":"2020-01-01T00:00:00Z","run_id":"r1"}\n',
            )

            r = subprocess.run(
                [sys.executable, "-m", "healthdelta", "export", "validate", "--input", str(nd)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout}\nstderr={r.stderr}")
            self.assertEqual(r.stdout.strip(), "ok")

    def test_validate_fails_on_missing_required_key(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            nd = root / "ndjson"
            nd.mkdir(parents=True, exist_ok=True)

            _write(
                nd / "observations.ndjson",
                '{"schema_version":2,"record_key":"k1","canonical_person_id":"p1","source":"healthkit","source_file":"source/export.xml","event_time":"2020-01-01T00:00:00Z"}\n',
            )

            r = subprocess.run(
                [sys.executable, "-m", "healthdelta", "export", "validate", "--input", str(nd)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 1, msg=f"stdout={r.stdout}\nstderr={r.stderr}")
            self.assertIn("missing_required_key", r.stderr)
            self.assertIn("run_id", r.stderr)

    def test_validate_fails_on_banned_token_when_configured(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            nd = root / "ndjson"
            nd.mkdir(parents=True, exist_ok=True)

            _write(
                nd / "documents.ndjson",
                '{"schema_version":2,"record_key":"k1","canonical_person_id":"p1","source":"fhir","source_file":"John Doe export/clinical-records/doc.json","event_time":"2020-01-02T00:00:00Z","run_id":"r1"}\n',
            )

            r = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "healthdelta",
                    "export",
                    "validate",
                    "--input",
                    str(nd),
                    "--banned-token",
                    "John Doe",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 1, msg=f"stdout={r.stdout}\nstderr={r.stderr}")
            self.assertIn("banned_token", r.stderr)

    def test_validate_fails_on_missing_trailing_newline(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            nd = root / "ndjson"
            nd.mkdir(parents=True, exist_ok=True)

            _write(
                nd / "conditions.ndjson",
                '{"schema_version":2,"record_key":"k1","canonical_person_id":"p1","source":"fhir","source_file":"x.json","event_time":"2020-01-01T00:00:00Z","run_id":"r1"}',
            )

            r = subprocess.run(
                [sys.executable, "-m", "healthdelta", "export", "validate", "--input", str(nd)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 1, msg=f"stdout={r.stdout}\nstderr={r.stderr}")
            self.assertIn("missing_trailing_newline", r.stderr)

    def test_validate_fails_on_unknown_schema_version(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            nd = root / "ndjson"
            nd.mkdir(parents=True, exist_ok=True)

            _write(
                nd / "observations.ndjson",
                '{"schema_version":3,"record_key":"k1","canonical_person_id":"p1","source":"healthkit","source_file":"source/export.xml","event_time":"2020-01-01T00:00:00Z","run_id":"r1"}\n',
            )

            r = subprocess.run(
                [sys.executable, "-m", "healthdelta", "export", "validate", "--input", str(nd)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 1, msg=f"stdout={r.stdout}\nstderr={r.stderr}")
            self.assertIn("schema_version_incompatible", r.stderr)

    def test_validate_diagnostic_reports_requires_report_contract_fields(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            nd = root / "ndjson"
            nd.mkdir(parents=True, exist_ok=True)

            _write(
                nd / "diagnostic_reports.ndjson",
                '{"schema_version":2,"record_key":"k1","canonical_person_id":"p1","source":"fhir","source_file":"source/clinical/dr.json","event_time":"2020-01-07T08:05:00Z","run_id":"r1","resource_type":"DiagnosticReport","source_id":"DiagnosticReport/dr1","status":"final"}\n',
            )

            r = subprocess.run(
                [sys.executable, "-m", "healthdelta", "export", "validate", "--input", str(nd)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 1, msg=f"stdout={r.stdout}\nstderr={r.stderr}")
            self.assertIn("missing_required_key", r.stderr)
            self.assertIn("diagnostic_report_id", r.stderr)

    def test_validate_documents_requires_document_reference_contract_fields(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            nd = root / "ndjson"
            nd.mkdir(parents=True, exist_ok=True)

            _write(
                nd / "documents.ndjson",
                '{"schema_version":2,"record_key":"k1","canonical_person_id":"p1","source":"fhir","source_file":"source/clinical/doc.json","event_time":"2020-01-02T03:04:05Z","run_id":"r1","resource_type":"DocumentReference","source_id":"DocumentReference/d1","status":"current"}\n',
            )

            r = subprocess.run(
                [sys.executable, "-m", "healthdelta", "export", "validate", "--input", str(nd)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 1, msg=f"stdout={r.stdout}\nstderr={r.stderr}")
            self.assertIn("missing_required_key", r.stderr)
            self.assertIn("document_reference_id", r.stderr)

    def test_validate_careplans_requires_careplan_contract_fields(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            nd = root / "ndjson"
            nd.mkdir(parents=True, exist_ok=True)

            _write(
                nd / "careplans.ndjson",
                '{"schema_version":2,"record_key":"k1","canonical_person_id":"p1","source":"fhir","source_file":"source/clinical/cp.json","event_time":"2020-01-10T00:00:00Z","run_id":"r1","resource_type":"CarePlan","source_id":"CarePlan/cp1","status":"active"}\n',
            )

            r = subprocess.run(
                [sys.executable, "-m", "healthdelta", "export", "validate", "--input", str(nd)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 1, msg=f"stdout={r.stdout}\nstderr={r.stderr}")
            self.assertIn("careplan_id", r.stderr)

    def test_validate_goals_requires_goal_contract_fields(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            nd = root / "ndjson"
            nd.mkdir(parents=True, exist_ok=True)

            _write(
                nd / "goals.ndjson",
                '{"schema_version":2,"record_key":"k1","canonical_person_id":"p1","source":"fhir","source_file":"source/clinical/g.json","event_time":"2020-01-09","run_id":"r1","resource_type":"Goal","source_id":"Goal/g1","status":"active"}\n',
            )

            r = subprocess.run(
                [sys.executable, "-m", "healthdelta", "export", "validate", "--input", str(nd)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 1, msg=f"stdout={r.stdout}\nstderr={r.stderr}")
            self.assertIn("goal_id", r.stderr)

    def test_validate_service_requests_requires_service_request_contract_fields(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            nd = root / "ndjson"
            nd.mkdir(parents=True, exist_ok=True)

            _write(
                nd / "service_requests.ndjson",
                '{"schema_version":2,"record_key":"k1","canonical_person_id":"p1","source":"fhir","source_file":"source/clinical/sr.json","event_time":"2020-01-11T00:00:00Z","run_id":"r1","resource_type":"ServiceRequest","source_id":"ServiceRequest/sr1","status":"active"}\n',
            )

            r = subprocess.run(
                [sys.executable, "-m", "healthdelta", "export", "validate", "--input", str(nd)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 1, msg=f"stdout={r.stdout}\nstderr={r.stderr}")
            self.assertIn("service_request_id", r.stderr)

    def test_validate_coverages_requires_coverage_contract_fields(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            nd = root / "ndjson"
            nd.mkdir(parents=True, exist_ok=True)

            _write(
                nd / "coverages.ndjson",
                '{"schema_version":2,"record_key":"k1","canonical_person_id":"p1","source":"fhir","source_file":"source/clinical/cv.json","event_time":"2020-01-12T00:00:00Z","run_id":"r1","resource_type":"Coverage","source_id":"Coverage/cv1","status":"active"}\n',
            )

            r = subprocess.run(
                [sys.executable, "-m", "healthdelta", "export", "validate", "--input", str(nd)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 1, msg=f"stdout={r.stdout}\nstderr={r.stderr}")
            self.assertIn("coverage_id", r.stderr)

    def test_validate_organizations_requires_organization_contract_fields(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            nd = root / "ndjson"
            nd.mkdir(parents=True, exist_ok=True)

            _write(
                nd / "organizations.ndjson",
                '{"schema_version":2,"record_key":"k1","canonical_person_id":"p1","source":"fhir","source_file":"source/clinical/org.json","event_time":"2020-01-12T00:00:00Z","run_id":"r1","resource_type":"Organization","source_id":"Organization/org1","name":"Example Hospital"}\n',
            )

            r = subprocess.run(
                [sys.executable, "-m", "healthdelta", "export", "validate", "--input", str(nd)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 1, msg=f"stdout={r.stdout}\nstderr={r.stderr}")
            self.assertIn("organization_id", r.stderr)

    def test_validate_practitioners_requires_practitioner_contract_fields(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            nd = root / "ndjson"
            nd.mkdir(parents=True, exist_ok=True)

            _write(
                nd / "practitioners.ndjson",
                '{"schema_version":2,"record_key":"k1","canonical_person_id":"p1","source":"fhir","source_file":"source/clinical/prac.json","event_time":"2020-01-12T00:00:00Z","run_id":"r1","resource_type":"Practitioner","source_id":"Practitioner/prac1","name":"Dr. Avery Stone"}\n',
            )

            r = subprocess.run(
                [sys.executable, "-m", "healthdelta", "export", "validate", "--input", str(nd)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 1, msg=f"stdout={r.stdout}\nstderr={r.stderr}")
            self.assertIn("practitioner_id", r.stderr)

    def test_validate_locations_requires_location_contract_fields(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            nd = root / "ndjson"
            nd.mkdir(parents=True, exist_ok=True)

            _write(
                nd / "locations.ndjson",
                '{"schema_version":2,"record_key":"k1","canonical_person_id":"p1","source":"fhir","source_file":"source/clinical/loc.json","event_time":"2020-01-12T00:00:00Z","run_id":"r1","resource_type":"Location","source_id":"Location/loc1","name":"North Wing Clinic"}\n',
            )

            r = subprocess.run(
                [sys.executable, "-m", "healthdelta", "export", "validate", "--input", str(nd)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 1, msg=f"stdout={r.stdout}\nstderr={r.stderr}")
            self.assertIn("location_id", r.stderr)

    def test_validate_provenance_requires_provenance_contract_fields(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            nd = root / "ndjson"
            nd.mkdir(parents=True, exist_ok=True)

            _write(
                nd / "provenance.ndjson",
                '{"schema_version":2,"record_key":"k1","canonical_person_id":"p1","source":"fhir","source_file":"source/clinical/prov.json","event_time":"2020-01-12T12:30:00Z","run_id":"r1","resource_type":"Provenance","source_id":"Provenance/prov1"}\n',
            )

            r = subprocess.run(
                [sys.executable, "-m", "healthdelta", "export", "validate", "--input", str(nd)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 1, msg=f"stdout={r.stdout}\nstderr={r.stderr}")
            self.assertIn("provenance_id", r.stderr)


if __name__ == "__main__":
    unittest.main()
