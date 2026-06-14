import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "profile_export"
FIXTURE_DIR_WRAPPED = Path(__file__).parent / "fixtures" / "profile_export_wrapped"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        return [row for row in r]


class TestExportProfile(unittest.TestCase):
    def test_export_profile_repairs_recoverable_cda(self) -> None:
        malformed_cda = """<?xml version="1.0"?>
<ClinicalDocument xmlns="urn:hl7-org:v3">
 <component>
  <section>
   <code code="11450-4" displayName="Problem List"/>
   <title>Problems</title>
  </section>
 </component>
</ClinicalDocument>
<component>
 <section>
  <code code="8716-3" displayName="Vital signs"/>
  <title>Vital Signs</title>
 </section>
</component>
"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            export_dir = root / "export"
            export_dir.mkdir(parents=True, exist_ok=True)
            (export_dir / "export.xml").write_text("<?xml version=\"1.0\" encoding=\"UTF-8\"?><HealthData></HealthData>\n", encoding="utf-8")
            (export_dir / "export_cda.xml").write_text(malformed_cda, encoding="utf-8")
            out = root / "out"
            from healthdelta.profile import build_export_profile

            build_export_profile(input_dir=str(export_dir), out_dir=str(out))

            inventory = json.loads((out / "clinical_inventory.json").read_text(encoding="utf-8"))
            self.assertEqual(inventory["summary"]["cda_section_total"], 2)

    def test_export_profile_fails_clearly_on_truncated_cda(self) -> None:
        truncated_cda = """<?xml version="1.0"?>
<ClinicalDocument xmlns="urn:hl7-org:v3">
 <component>
  <section>
   <title>Vital Signs</title>
"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            export_dir = root / "export"
            export_dir.mkdir(parents=True, exist_ok=True)
            (export_dir / "export.xml").write_text("<?xml version=\"1.0\" encoding=\"UTF-8\"?><HealthData></HealthData>\n", encoding="utf-8")
            (export_dir / "export_cda.xml").write_text(truncated_cda, encoding="utf-8")
            out = root / "out"
            from healthdelta.cda_xml import CdaRepairError
            from healthdelta.profile import build_export_profile

            with self.assertRaises(CdaRepairError) as cm:
                build_export_profile(input_dir=str(export_dir), out_dir=str(out))
            self.assertIn("dave0875@gmail.com", str(cm.exception))

    def test_export_profile_is_deterministic_and_share_safe(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out"

            cmd = [
                sys.executable,
                "-m",
                "healthdelta",
                "export",
                "profile",
                "--input",
                str(FIXTURE_DIR),
                "--out",
                str(out),
                "--sample-json",
                "2",
                "--top-files",
                "3",
            ]
            r1 = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(r1.returncode, 0, msg=f"stdout={r1.stdout}\nstderr={r1.stderr}")

            expected_outputs = [
                out / "profile.json",
                out / "profile.md",
                out / "clinical_coverage_inventory.json",
                out / "clinical_inventory.json",
                out / "files_top.csv",
                out / "counts_by_ext.csv",
                out / "healthkit_record_types.csv",
                out / "clinical_resource_types.csv",
                out / "clinical_schema_keys.csv",
                out / "sensitive_field_map.json",
                out / "cda_tag_counts.csv",
            ]
            for p in expected_outputs:
                self.assertTrue(p.exists(), msg=f"missing {p}")
                self.assertTrue(p.read_bytes().endswith(b"\n"), msg=f"not newline-terminated: {p}")

            before = {p.name: p.read_bytes() for p in expected_outputs}

            # Rerun and assert byte-stability.
            r2 = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(r2.returncode, 0, msg=f"stdout={r2.stdout}\nstderr={r2.stderr}")
            for p in expected_outputs:
                self.assertEqual(p.read_bytes(), before[p.name], msg=f"changed on rerun: {p}")

            combined = b"".join(before.values()).decode("utf-8", errors="replace")
            md = (out / "profile.md").read_text(encoding="utf-8")
            self.assertIn("## Next Steps", md)
            self.assertIn("`healthdelta run all --input <export_dir> --out data --mode share`", md)
            self.assertIn("`healthdelta pipeline run --input <export_dir> --out data --mode share`", md)
            for banned in [
                "John Doe",
                "1980-01-02",
                "19800102",
                "2020-01-01",
                "discharge summary free text",
            ]:
                self.assertNotIn(banned, combined)

            prof = json.loads((out / "profile.json").read_text(encoding="utf-8"))
            self.assertEqual(prof["schema_version"], 1)
            self.assertTrue(isinstance(prof.get("profile_id"), str) and len(prof["profile_id"]) == 64)
            self.assertEqual(prof["summary"]["file_count"], 5)
            self.assertEqual(prof["summary"]["clinical_json_total_files"], 3)
            self.assertEqual(prof["summary"]["clinical_json_sampled_files"], 2)

            inventory = json.loads((out / "clinical_coverage_inventory.json").read_text(encoding="utf-8"))
            inventory_alias = json.loads((out / "clinical_inventory.json").read_text(encoding="utf-8"))
            self.assertEqual(inventory["schema_version"], 1)
            self.assertEqual(inventory["profile_id"], prof["profile_id"])
            self.assertEqual(inventory_alias, inventory)
            self.assertEqual(
                inventory["fhir_resource_types"],
                [
                    {"resourceType": "Observation", "count": 1},
                    {"resourceType": "Patient", "count": 1},
                ],
            )
            self.assertEqual(
                inventory["cda_sections"],
                [
                    {
                        "section_code": "8716-3",
                        "section_display": "Vital signs",
                        "section_title": "Vital Signs",
                        "count": 1,
                    }
                ],
            )

            # counts_by_ext.csv should include .json=3, .xml=2
            ext_rows = _read_csv(out / "counts_by_ext.csv")
            ext_map = {r["ext"]: int(r["count"]) for r in ext_rows}
            self.assertEqual(ext_map.get(".json"), 3)
            self.assertEqual(ext_map.get(".xml"), 2)

            # files_top.csv ordering is deterministic: size desc, path asc.
            files = []
            for p in FIXTURE_DIR.rglob("*"):
                if p.is_file():
                    files.append((p.stat().st_size, p.relative_to(FIXTURE_DIR).as_posix()))
            files_sorted = sorted(files, key=lambda x: (-x[0], x[1]))[:3]
            top_rows = _read_csv(out / "files_top.csv")
            self.assertEqual(len(top_rows), 3)
            self.assertEqual([(int(r["size_bytes"]), r["path"]) for r in top_rows], files_sorted)

            # HealthKit record types.
            hk_rows = _read_csv(out / "healthkit_record_types.csv")
            hk_map = {r["type"]: int(r["count"]) for r in hk_rows}
            self.assertEqual(hk_map.get("HKQuantityTypeIdentifierHeartRate"), 2)
            self.assertEqual(hk_map.get("HKQuantityTypeIdentifierStepCount"), 1)

            # Clinical resource types: sampled first 2 files => Observation + Patient.
            fhir_rows = _read_csv(out / "clinical_resource_types.csv")
            fhir = [(r["resourceType"], int(r["count"])) for r in fhir_rows]
            self.assertEqual(fhir, [("Observation", 1), ("Patient", 1)])

            schema_rows = _read_csv(out / "clinical_schema_keys.csv")
            schema_paths = {(r["resourceType"], r["path"]) for r in schema_rows}
            self.assertIn(("Patient", "birthDate"), schema_paths)
            self.assertIn(("Patient", "name[].text"), schema_paths)
            self.assertIn(("Observation", "subject.display"), schema_paths)

            sensitive = json.loads((out / "sensitive_field_map.json").read_text(encoding="utf-8"))
            self.assertIn("sensitive_fields", sensitive)
            self.assertIn("sensitive_paths_observed", sensitive)
            by_field = {x["field"]: x for x in sensitive["sensitive_fields"]}
            self.assertTrue(by_field["name"]["observed"])
            self.assertTrue(by_field["birthDate"]["observed"])
            self.assertTrue(by_field["display"]["observed"])
            self.assertFalse(by_field["address"]["observed"])

            # CDA tag counts: should include expected tags and not include attributes/text.
            cda_rows = _read_csv(out / "cda_tag_counts.csv")
            cda_map = {r["tag"]: int(r["count"]) for r in cda_rows}
            self.assertEqual(cda_map.get("ClinicalDocument"), 1)
            self.assertEqual(cda_map.get("observation"), 2)

    def test_export_profile_supports_wrapped_apple_health_export_root(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out"

            cmd = [
                sys.executable,
                "-m",
                "healthdelta",
                "export",
                "profile",
                "--input",
                str(FIXTURE_DIR_WRAPPED),
                "--out",
                str(out),
                "--sample-json",
                "10",
                "--top-files",
                "10",
            ]
            r1 = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(r1.returncode, 0, msg=f"stdout={r1.stdout}\nstderr={r1.stderr}")

            prof = json.loads((out / "profile.json").read_text(encoding="utf-8"))
            self.assertEqual(prof["summary"]["export_root_rel"], "apple_health_export")

            # Ensure unrelated outer file is not included in file list outputs.
            top_rows = _read_csv(out / "files_top.csv")
            paths = [r["path"] for r in top_rows]
            self.assertNotIn("README.txt", paths)

            combined = b"".join(p.read_bytes() for p in out.iterdir() if p.is_file()).decode("utf-8", errors="replace")
            md = (out / "profile.md").read_text(encoding="utf-8")
            self.assertIn("## Next Steps", md)
            self.assertIn("`healthdelta run all --input <export_dir> --out data --mode share`", md)
            for banned in ["John Doe", "1980-01-02", "19800102"]:
                self.assertNotIn(banned, combined)

    def test_export_profile_writes_zero_clinical_inventory_when_no_clinical_records_exist(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            export_dir = root / "export"
            export_dir.mkdir(parents=True, exist_ok=True)
            (export_dir / "export.xml").write_text("<?xml version=\"1.0\" encoding=\"UTF-8\"?><HealthData></HealthData>\n", encoding="utf-8")
            out = root / "out"

            cmd = [
                sys.executable,
                "-m",
                "healthdelta",
                "export",
                "profile",
                "--input",
                str(export_dir),
                "--out",
                str(out),
                "--sample-json",
                "10",
                "--top-files",
                "10",
            ]
            run = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, msg=f"stdout={run.stdout}\nstderr={run.stderr}")

            inventory = json.loads((out / "clinical_inventory.json").read_text(encoding="utf-8"))
            self.assertEqual(inventory["fhir_resource_types"], [])
            self.assertEqual(inventory["cda_sections"], [])
            self.assertEqual(inventory["summary"]["clinical_json_total_files"], 0)
            self.assertEqual(inventory["summary"]["cda_section_total"], 0)

    def test_export_coverage_writes_share_safe_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "coverage"
            cmd = [
                sys.executable,
                "-m",
                "healthdelta",
                "export",
                "coverage",
                "--input",
                str(FIXTURE_DIR),
                "--out",
                str(out),
            ]
            run1 = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(run1.returncode, 0, msg=f"stdout={run1.stdout}\nstderr={run1.stderr}")
            j1 = (out / "coverage_matrix.json").read_bytes()
            m1 = (out / "coverage_matrix.md").read_bytes()
            run2 = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(run2.returncode, 0, msg=f"stdout={run2.stdout}\nstderr={run2.stderr}")
            self.assertEqual((out / "coverage_matrix.json").read_bytes(), j1)
            self.assertEqual((out / "coverage_matrix.md").read_bytes(), m1)

            matrix = json.loads(j1.decode("utf-8"))
            self.assertEqual(
                matrix["resource_types"],
                [
                    {"count": 1, "has_canonical_mapping": False, "resourceType": "Patient"},
                    {"count": 1, "has_canonical_mapping": True, "resourceType": "DocumentReference"},
                    {"count": 1, "has_canonical_mapping": True, "resourceType": "Observation"},
                ],
            )
            self.assertEqual(matrix["top_unmapped_resource_types"], [{"count": 1, "has_canonical_mapping": False, "resourceType": "Patient"}])
            self.assertEqual(matrix["cda_sections"][0]["section_title"], "Vital Signs")
            md = m1.decode("utf-8")
            self.assertIn("## Top Unmapped Resources", md)
            self.assertIn("Patient: 1", md)


if __name__ == "__main__":
    unittest.main()
