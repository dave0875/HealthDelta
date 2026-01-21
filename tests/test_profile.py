import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "profile_export"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        return [row for row in r]


class TestExportProfile(unittest.TestCase):
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
                out / "files_top.csv",
                out / "counts_by_ext.csv",
                out / "healthkit_record_types.csv",
                out / "clinical_resource_types.csv",
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

            # CDA tag counts: should include expected tags and not include attributes/text.
            cda_rows = _read_csv(out / "cda_tag_counts.csv")
            cda_map = {r["tag"]: int(r["count"]) for r in cda_rows}
            self.assertEqual(cda_map.get("ClinicalDocument"), 1)
            self.assertEqual(cda_map.get("observation"), 2)


if __name__ == "__main__":
    unittest.main()

