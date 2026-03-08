import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _duckdb_available() -> bool:
    try:
        import duckdb  # noqa: F401

        return True
    except Exception:
        return False


class TestDuckdbLoader(unittest.TestCase):
    @unittest.skipUnless(_duckdb_available(), "duckdb not installed in this environment")
    def test_duckdb_build_and_query_are_deterministic_and_pii_free(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ndjson = root / "ndjson"
            ndjson.mkdir(parents=True, exist_ok=True)

            # Synthetic PII-like strings that must not appear in schema or query outputs.
            pii_name = "John Doe"
            pii_dob = "1980-01-02"
            pii_patient_id = "Patient/p1"

            observations = "\n".join(
                [
                    # healthkit observation row (plus extra fields that should be ignored)
                    '{"schema_version":2,"record_key":"k1","canonical_person_id":"person-1","source":"healthkit","source_system":"ss_healthkit","source_file":"source/export.xml","event_time":"2020-01-01T05:00:00Z","run_id":"run-1","event_key":"k1","hk_type":"HKQuantityTypeIdentifierHeartRate","value":"72","unit":"count/min","pii_name":"%s","dob":"%s"}'
                    % (pii_name, pii_dob),
                    # fhir observation row
                    '{"schema_version":2,"record_key":"k2","canonical_person_id":"person-1","source":"fhir","source_system":"ss_fhir","source_file":"source/clinical/obs.json","event_time":"2020-01-01T01:02:03Z","run_id":"run-1","event_key":"k2","resource_type":"Observation","source_id":"Observation/o1","value":72,"unit":"count/min","pii_id":"%s"}'
                    % pii_patient_id,
                    # cda observation row
                    '{"schema_version":2,"record_key":"k3","canonical_person_id":"person-1","source":"cda","source_system":"ss_cda","source_file":"source/unpacked/export_cda.xml","event_time":"2020-01-01T11:22:33Z","run_id":"run-1","event_key":"k3","code":"8867-4","value":"72","unit":"/min"}',
                ]
            )
            _write_text(ndjson / "observations.ndjson", observations + "\n")

            documents = (
                '{"schema_version":2,"record_key":"d1","canonical_person_id":"person-1","source":"fhir","source_system":"ss_fhir","source_file":"source/clinical/doc.json","event_time":"2020-01-02T03:04:05Z","run_id":"run-1","event_key":"d1","resource_type":"DocumentReference","source_id":"DocumentReference/d1","status":"current"}\n'
            )
            _write_text(ndjson / "documents.ndjson", documents)

            medications = "\n".join(
                [
                    '{"schema_version":2,"record_key":"m1","canonical_person_id":"person-1","source":"fhir","source_system":"ss_fhir","source_file":"source/clinical/med_request.json","event_time":"2020-01-03T00:00:00Z","run_id":"run-1","event_key":"m1","resource_type":"MedicationRequest","source_id":"MedicationRequest/m1","status":"active"}',
                    '{"schema_version":2,"record_key":"m2","canonical_person_id":"person-1","source":"fhir","source_system":"ss_fhir","source_file":"source/clinical/med_statement.json","event_time":"2020-01-03T08:30:00Z","run_id":"run-1","event_key":"m2","resource_type":"MedicationStatement","source_id":"MedicationStatement/m2","status":"active"}',
                    '{"schema_version":2,"record_key":"m3","canonical_person_id":"person-1","source":"fhir","source_system":"ss_fhir","source_file":"source/clinical/med_dispense.json","event_time":"2020-01-03T09:45:00Z","run_id":"run-1","event_key":"m3","resource_type":"MedicationDispense","source_id":"MedicationDispense/m3","status":"completed"}',
                ]
            ) + "\n"
            _write_text(ndjson / "medications.ndjson", medications)

            conditions = (
                '{"schema_version":2,"record_key":"c1","canonical_person_id":"person-1","source":"fhir","source_system":"ss_fhir","source_file":"source/clinical/cond.json","event_time":"2020-01-04T00:00:00Z","run_id":"run-1","event_key":"c1","resource_type":"Condition","source_id":"Condition/c1"}\n'
            )
            _write_text(ndjson / "conditions.ndjson", conditions)

            encounters = (
                '{"schema_version":2,"record_key":"e1","canonical_person_id":"person-1","source":"fhir","source_system":"ss_fhir","source_file":"source/clinical/encounter.json","event_time":"2020-01-05T10:00:00Z","run_id":"run-1","event_key":"e1","resource_type":"Encounter","source_id":"Encounter/e1","status":"finished"}\n'
            )
            _write_text(ndjson / "encounters.ndjson", encounters)

            procedures = (
                '{"schema_version":2,"record_key":"p1","canonical_person_id":"person-1","source":"fhir","source_system":"ss_fhir","source_file":"source/clinical/procedure.json","event_time":"2020-01-06T09:30:00Z","run_id":"run-1","event_key":"p1","resource_type":"Procedure","source_id":"Procedure/p1","status":"completed"}\n'
            )
            _write_text(ndjson / "procedures.ndjson", procedures)
            diagnostic_reports = (
                '{"schema_version":2,"record_key":"dr1","canonical_person_id":"person-1","source":"fhir","source_system":"ss_fhir","source_file":"source/clinical/diag_report.json","event_time":"2020-01-07T08:00:00Z","run_id":"run-1","event_key":"dr1","resource_type":"DiagnosticReport","source_id":"DiagnosticReport/dr1","status":"final"}\n'
            )
            _write_text(ndjson / "diagnostic_reports.ndjson", diagnostic_reports)

            db_path = root / "out.duckdb"

            build = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "healthdelta",
                    "duckdb",
                    "build",
                    "--input",
                    str(ndjson),
                    "--db",
                    str(db_path),
                    "--replace",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(build.returncode, 0, msg=f"stdout={build.stdout}\nstderr={build.stderr}")
            self.assertTrue(db_path.exists())

            # Verify tables exist and row counts.
            q1 = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "healthdelta",
                    "duckdb",
                    "query",
                    "--db",
                    str(db_path),
                    "--sql",
                    "SELECT COUNT(*) AS n FROM observations ORDER BY n;",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(q1.returncode, 0, msg=f"stdout={q1.stdout}\nstderr={q1.stderr}")
            rows = list(csv.DictReader(q1.stdout.splitlines()))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["n"], "3")

            q2 = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "healthdelta",
                    "duckdb",
                    "query",
                    "--db",
                    str(db_path),
                    "--sql",
                    "SELECT COUNT(*) AS n FROM documents ORDER BY n;",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(q2.returncode, 0, msg=f"stdout={q2.stdout}\nstderr={q2.stderr}")
            rows = list(csv.DictReader(q2.stdout.splitlines()))
            self.assertEqual(rows[0]["n"], "1")

            q3 = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "healthdelta",
                    "duckdb",
                    "query",
                    "--db",
                    str(db_path),
                    "--sql",
                    "SELECT COUNT(*) AS n FROM encounters ORDER BY n;",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(q3.returncode, 0, msg=f"stdout={q3.stdout}\nstderr={q3.stderr}")
            rows = list(csv.DictReader(q3.stdout.splitlines()))
            self.assertEqual(rows[0]["n"], "1")

            q4 = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "healthdelta",
                    "duckdb",
                    "query",
                    "--db",
                    str(db_path),
                    "--sql",
                    "SELECT COUNT(*) AS n FROM procedures ORDER BY n;",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(q4.returncode, 0, msg=f"stdout={q4.stdout}\nstderr={q4.stderr}")
            rows = list(csv.DictReader(q4.stdout.splitlines()))
            self.assertEqual(rows[0]["n"], "1")

            q5 = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "healthdelta",
                    "duckdb",
                    "query",
                    "--db",
                    str(db_path),
                    "--sql",
                    "SELECT COUNT(*) AS n FROM diagnostic_reports ORDER BY n;",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(q5.returncode, 0, msg=f"stdout={q5.stdout}\nstderr={q5.stderr}")
            rows = list(csv.DictReader(q5.stdout.splitlines()))
            self.assertEqual(rows[0]["n"], "1")

            q6 = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "healthdelta",
                    "duckdb",
                    "query",
                    "--db",
                    str(db_path),
                    "--sql",
                    "SELECT resource_type, COUNT(*) AS n FROM medications GROUP BY resource_type ORDER BY resource_type;",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(q6.returncode, 0, msg=f"stdout={q6.stdout}\nstderr={q6.stderr}")
            rows = list(csv.DictReader(q6.stdout.splitlines()))
            self.assertEqual(
                rows,
                [
                    {"resource_type": "MedicationDispense", "n": "1"},
                    {"resource_type": "MedicationRequest", "n": "1"},
                    {"resource_type": "MedicationStatement", "n": "1"},
                ],
            )

            # Ensure the loader did not introduce PII into query output.
            combined_out = q1.stdout + q2.stdout + q3.stdout + q4.stdout + q5.stdout + q6.stdout
            self.assertNotIn(pii_name, combined_out)
            self.assertNotIn(pii_dob, combined_out)
            self.assertNotIn(pii_patient_id, combined_out)

            # Rebuild without --replace must be append-safe (no duplicates) for the same inputs.
            build2 = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "healthdelta",
                    "duckdb",
                    "build",
                    "--input",
                    str(ndjson),
                    "--db",
                    str(db_path),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(build2.returncode, 0, msg=f"stdout={build2.stdout}\nstderr={build2.stderr}")

            # Row counts should remain stable on rerun.
            q1b = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "healthdelta",
                    "duckdb",
                    "query",
                    "--db",
                    str(db_path),
                    "--sql",
                    "SELECT COUNT(*) AS n FROM observations ORDER BY n;",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(q1b.returncode, 0, msg=f"stdout={q1b.stdout}\nstderr={q1b.stderr}")
            rows = list(csv.DictReader(q1b.stdout.splitlines()))
            self.assertEqual(rows[0]["n"], "3")
