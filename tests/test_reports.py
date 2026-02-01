import csv
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


def _read_csv(path: Path) -> list[dict]:
    return list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))


class TestReports(unittest.TestCase):
    @unittest.skipUnless(_duckdb_available(), "duckdb not installed in this environment")
    def test_report_build_writes_deterministic_share_safe_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ndjson = root / "ndjson"
            ndjson.mkdir(parents=True, exist_ok=True)

            pii_name = "John Doe"
            pii_dob = "1980-01-02"
            pii_patient_id = "Patient/p1"

            _write_text(
                ndjson / "observations.ndjson",
                "\n".join(
                    [
                        '{"canonical_person_id":"person-1","source":"healthkit","source_system":"ss_healthkit","source_file":"source/export.xml","event_time":"2020-01-01T05:00:00Z","run_id":"run-1","event_key":"k1","hk_type":"HKQuantityTypeIdentifierHeartRate","value":"72","unit":"count/min","pii_name":"%s","dob":"%s"}'
                        % (pii_name, pii_dob),
                        '{"canonical_person_id":"person-1","source":"fhir","source_system":"ss_fhir","source_file":"source/clinical/obs.json","event_time":"2020-01-01T01:02:03Z","run_id":"run-1","event_key":"k2","resource_type":"Observation","source_id":"Observation/o1","value":72,"unit":"count/min","pii_id":"%s"}'
                        % pii_patient_id,
                        '{"canonical_person_id":"person-1","source":"cda","source_system":"ss_cda","source_file":"source/unpacked/export_cda.xml","event_time":"2020-01-01T11:22:33Z","run_id":"run-1","event_key":"k3","code":"8867-4","value":"72","unit":"/min"}',
                        '{"canonical_person_id":"person-1","source":"fhir","source_system":"ss_fhir","source_file":"source/clinical/immunization.json","event_time":"2020-01-08T09:00:00Z","run_id":"run-1","event_key":"i1","resource_type":"Immunization","source_id":"Immunization/i1","status":"completed"}',
                    ]
                )
                + "\n",
            )
            _write_text(
                ndjson / "documents.ndjson",
                '{"canonical_person_id":"person-1","source":"fhir","source_system":"ss_fhir","source_file":"source/clinical/doc.json","event_time":"2020-01-02T03:04:05Z","run_id":"run-1","event_key":"d1","resource_type":"DocumentReference","source_id":"DocumentReference/d1","status":"current"}\n',
            )
            _write_text(
                ndjson / "medications.ndjson",
                '{"canonical_person_id":"person-1","source":"fhir","source_system":"ss_fhir","source_file":"source/clinical/med.json","event_time":"2020-01-03T00:00:00Z","run_id":"run-1","event_key":"m1","resource_type":"MedicationRequest","source_id":"MedicationRequest/m1","status":"active"}\n',
            )
            _write_text(
                ndjson / "conditions.ndjson",
                "\n".join(
                    [
                        '{"canonical_person_id":"person-1","source":"fhir","source_system":"ss_fhir","source_file":"source/clinical/cond.json","event_time":"2020-01-04T00:00:00Z","run_id":"run-1","event_key":"c1","resource_type":"Condition","source_id":"Condition/c1","code":"I10"}',
                        '{"canonical_person_id":"person-1","source":"fhir","source_system":"ss_fhir","source_file":"source/clinical/allergy.json","event_time":"2020-01-04T07:00:00Z","run_id":"run-1","event_key":"a1","resource_type":"AllergyIntolerance","source_id":"AllergyIntolerance/a1"}',
                    ]
                )
                + "\n",
            )
            _write_text(
                ndjson / "encounters.ndjson",
                '{"canonical_person_id":"person-1","source":"fhir","source_system":"ss_fhir","source_file":"source/clinical/encounter.json","event_time":"2020-01-05T10:00:00Z","run_id":"run-1","event_key":"e1","resource_type":"Encounter","source_id":"Encounter/e1","status":"finished"}\n',
            )
            _write_text(
                ndjson / "procedures.ndjson",
                '{"canonical_person_id":"person-1","source":"fhir","source_system":"ss_fhir","source_file":"source/clinical/procedure.json","event_time":"2020-01-06T09:30:00Z","run_id":"run-1","event_key":"p1","resource_type":"Procedure","source_id":"Procedure/p1","status":"completed"}\n',
            )
            _write_text(
                ndjson / "diagnostic_reports.ndjson",
                '{"canonical_person_id":"person-1","source":"fhir","source_system":"ss_fhir","source_file":"source/clinical/diag_report.json","event_time":"2020-01-07T08:00:00Z","run_id":"run-1","event_key":"dr1","resource_type":"DiagnosticReport","source_id":"DiagnosticReport/dr1","status":"final"}\n',
            )

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

            out_dir = root / "report"
            run1 = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "healthdelta",
                    "report",
                    "build",
                    "--db",
                    str(db_path),
                    "--out",
                    str(out_dir),
                    "--mode",
                    "share",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(run1.returncode, 0, msg=f"stdout={run1.stdout}\nstderr={run1.stderr}")

            expected_paths = [
                out_dir / "summary.json",
                out_dir / "summary.md",
                out_dir / "coverage_by_person.csv",
                out_dir / "coverage_by_source.csv",
                out_dir / "coverage_by_source_system.csv",
                out_dir / "timeline_daily_counts.csv",
                out_dir / "reference_integrity_unresolved.csv",
            ]
            for p in expected_paths:
                self.assertTrue(p.exists(), msg=f"missing {p}")
                self.assertTrue(p.read_bytes().endswith(b"\n"), msg=f"not newline-terminated: {p}")

            before_json = (out_dir / "summary.json").read_bytes()
            before_md = (out_dir / "summary.md").read_bytes()

            summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["tables"]["observations"]["total_rows"], 4)
            self.assertEqual(summary["tables"]["documents"]["total_rows"], 1)
            self.assertEqual(summary["tables"]["medications"]["total_rows"], 1)
            self.assertEqual(summary["tables"]["conditions"]["total_rows"], 2)
            self.assertEqual(summary["tables"]["encounters"]["total_rows"], 1)
            self.assertEqual(summary["tables"]["procedures"]["total_rows"], 1)
            self.assertEqual(summary["tables"]["diagnostic_reports"]["total_rows"], 1)
            self.assertEqual(summary["reference_integrity"]["unresolved_reference_rows_total"], 0)

            self.assertEqual(summary["tables"]["observations"]["min_event_time"], "2020-01-01T01:02:03Z")
            self.assertEqual(summary["tables"]["observations"]["max_event_time"], "2020-01-08T09:00:00Z")

            per_person = {p["canonical_person_id"]: p for p in summary["per_person"]}
            self.assertIn("person-1", per_person)
            self.assertEqual(per_person["person-1"]["rows_by_table"]["observations"], 4)
            self.assertEqual(per_person["person-1"]["rows_by_table"]["documents"], 1)
            self.assertEqual(per_person["person-1"]["rows_by_table"]["medications"], 1)
            self.assertEqual(per_person["person-1"]["rows_by_table"]["conditions"], 2)
            self.assertEqual(per_person["person-1"]["rows_by_table"]["encounters"], 1)
            self.assertEqual(per_person["person-1"]["rows_by_table"]["procedures"], 1)
            self.assertEqual(per_person["person-1"]["rows_by_table"]["diagnostic_reports"], 1)
            self.assertEqual(per_person["person-1"]["min_event_time"], "2020-01-01T01:02:03Z")
            self.assertEqual(per_person["person-1"]["max_event_time"], "2020-01-08T09:00:00Z")

            by_source = _read_csv(out_dir / "coverage_by_source.csv")
            # Stable expectations: stream+source rows
            expected = {
                ("observations", "cda"): "1",
                ("observations", "healthkit"): "1",
                ("observations", "fhir"): "2",
                ("documents", "fhir"): "1",
                ("medications", "fhir"): "1",
                ("conditions", "fhir"): "2",
                ("encounters", "fhir"): "1",
                ("procedures", "fhir"): "1",
                ("diagnostic_reports", "fhir"): "1",
            }
            got = {(r["stream"], r["source"]): r["rows"] for r in by_source}
            for k, v in expected.items():
                self.assertEqual(got.get(k), v)

            by_source_system = _read_csv(out_dir / "coverage_by_source_system.csv")
            ss = {(r["stream"], r["source_system"]): r["rows"] for r in by_source_system}
            self.assertEqual(ss.get(("observations", "ss_fhir")), "2")
            self.assertEqual(ss.get(("observations", "ss_healthkit")), "1")
            self.assertEqual(ss.get(("observations", "ss_cda")), "1")

            timeline = _read_csv(out_dir / "timeline_daily_counts.csv")
            # day is YYYY-MM-DD
            day_stream_source = {(r["day"], r["stream"], r["source"]): r["rows"] for r in timeline}
            self.assertEqual(day_stream_source.get(("2020-01-01", "observations", "healthkit")), "1")
            self.assertEqual(day_stream_source.get(("2020-01-01", "observations", "fhir")), "1")
            self.assertEqual(day_stream_source.get(("2020-01-01", "observations", "cda")), "1")
            self.assertEqual(day_stream_source.get(("2020-01-08", "observations", "fhir")), "1")
            self.assertEqual(day_stream_source.get(("2020-01-02", "documents", "fhir")), "1")
            self.assertEqual(day_stream_source.get(("2020-01-05", "encounters", "fhir")), "1")
            self.assertEqual(day_stream_source.get(("2020-01-06", "procedures", "fhir")), "1")
            self.assertEqual(day_stream_source.get(("2020-01-07", "diagnostic_reports", "fhir")), "1")

            combined = "".join(p.read_text(encoding="utf-8") for p in expected_paths)
            self.assertNotIn(pii_name, combined)
            self.assertNotIn(pii_dob, combined)
            self.assertNotIn(pii_patient_id, combined)

            # Rerun should overwrite deterministically
            run2 = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "healthdelta",
                    "report",
                    "build",
                    "--db",
                    str(db_path),
                    "--out",
                    str(out_dir),
                    "--mode",
                    "share",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(run2.returncode, 0, msg=f"stdout={run2.stdout}\nstderr={run2.stderr}")
            self.assertEqual((out_dir / "summary.json").read_bytes(), before_json)
            self.assertEqual((out_dir / "summary.md").read_bytes(), before_md)

    @unittest.skipUnless(_duckdb_available(), "duckdb not installed in this environment")
    def test_report_build_writes_unresolved_reference_integrity_report(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ndjson = root / "ndjson"
            ndjson.mkdir(parents=True, exist_ok=True)

            _write_text(
                ndjson / "encounters.ndjson",
                "\n".join(
                    [
                        '{"canonical_person_id":"person-1","source":"fhir","source_system":"ss_fhir","source_file":"source/clinical/encounter_ok.json","event_time":"2020-01-05T10:00:00Z","run_id":"run-1","event_key":"e-ok","resource_type":"Encounter","source_id":"Encounter/e-ok","status":"finished"}',
                        '{"canonical_person_id":"unresolved","source":"fhir","source_system":"ss_fhir","source_file":"source/clinical/encounter_bad_1.json","event_time":"2020-01-05T11:00:00Z","run_id":"run-1","event_key":"e-bad-1","resource_type":"Encounter","source_id":"Encounter/e-bad-1","status":"finished"}',
                        '{"canonical_person_id":"unresolved","source":"fhir","source_system":"ss_fhir","source_file":"source/clinical/encounter_bad_2.json","event_time":"2020-01-05T12:00:00Z","run_id":"run-1","event_key":"e-bad-2","resource_type":"Encounter","source_id":"Encounter/e-bad-2","status":"finished"}',
                    ]
                )
                + "\n",
            )
            _write_text(
                ndjson / "procedures.ndjson",
                '{"canonical_person_id":"unresolved","source":"fhir","source_system":"ss_fhir","source_file":"source/clinical/procedure_bad.json","event_time":"2020-01-06T09:30:00Z","run_id":"run-1","event_key":"p-bad-1","resource_type":"Procedure","source_id":"Procedure/p-bad-1","status":"completed"}\n',
            )
            _write_text(
                ndjson / "observations.ndjson",
                '{"canonical_person_id":"unresolved","source":"fhir","source_system":"ss_fhir","source_file":"source/clinical/immunization_bad.json","event_time":"2020-01-08T09:00:00Z","run_id":"run-1","event_key":"i-bad-1","resource_type":"Immunization","source_id":"Immunization/i-bad-1","status":"completed"}\n',
            )
            _write_text(ndjson / "documents.ndjson", "\n")
            _write_text(ndjson / "medications.ndjson", "\n")
            _write_text(ndjson / "conditions.ndjson", "\n")

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

            out_dir = root / "report"
            run1 = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "healthdelta",
                    "report",
                    "build",
                    "--db",
                    str(db_path),
                    "--out",
                    str(out_dir),
                    "--mode",
                    "share",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(run1.returncode, 0, msg=f"stdout={run1.stdout}\nstderr={run1.stderr}")

            rows = _read_csv(out_dir / "reference_integrity_unresolved.csv")
            got = {(r["reference_type"]): r["rows"] for r in rows}
            self.assertEqual(got.get("Encounter.subject"), "2")
            self.assertEqual(got.get("Procedure.subject"), "1")
            self.assertEqual(got.get("Immunization.patient"), "1")

            summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            integrity = summary.get("reference_integrity")
            self.assertIsInstance(integrity, dict)
            self.assertEqual(integrity.get("unresolved_reference_rows_total"), 4)


if __name__ == "__main__":
    unittest.main()
