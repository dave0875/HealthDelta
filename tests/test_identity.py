import json
import tempfile
import unittest
from pathlib import Path

from healthdelta.identity import parse_name


def _write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class TestNameParsing(unittest.TestCase):
    def test_parse_first_last(self) -> None:
        parsed = parse_name("John Doe")
        self.assertEqual(parsed.first_norm, "john")
        self.assertEqual(parsed.last_norm, "doe")

    def test_parse_last_comma_first(self) -> None:
        parsed = parse_name("Doe, John")
        self.assertEqual(parsed.first_norm, "john")
        self.assertEqual(parsed.last_norm, "doe")

    def test_normalization_whitespace_and_case(self) -> None:
        parsed = parse_name("  jOhN    dOE  ")
        self.assertEqual(parsed.first_norm, "john")
        self.assertEqual(parsed.last_norm, "doe")

    def test_different_people_same_last_name(self) -> None:
        a = parse_name("John Doe")
        b = parse_name("Jane Doe")
        self.assertEqual(a.last_norm, b.last_norm)
        self.assertNotEqual(a.first_norm, b.first_norm)


class TestIdentityBuild(unittest.TestCase):
    def test_build_creates_unverified_person_link_when_unambiguous(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            run_dir = root / "staging" / "run123"
            clinical_rel = "source/unpacked/clinical/patient.json"
            (run_dir / "source" / "unpacked" / "clinical").mkdir(parents=True, exist_ok=True)

            patient_bundle = {
                "resourceType": "Bundle",
                "entry": [
                    {
                        "resource": {
                            "resourceType": "Patient",
                            "id": "p1",
                            "name": [{"text": "John Doe"}],
                            "identifier": [{"system": "sysA", "value": "111"}],
                        }
                    },
                ],
            }
            _write_json(run_dir / clinical_rel, patient_bundle)

            layout = {"run_id": "run123", "export_xml": "source/unpacked/export.xml", "clinical_json": [clinical_rel]}
            _write_json(run_dir / "layout.json", layout)

            # Run in a temp cwd to keep outputs under that temp tree
            old_cwd = Path.cwd()
            try:
                import os

                os.chdir(root)
                from healthdelta.identity import build_identity

                build_identity(staging_run_dir=str(run_dir))
            finally:
                os.chdir(old_cwd)

            people = json.loads((root / "data" / "identity" / "people.json").read_text(encoding="utf-8"))
            aliases = json.loads((root / "data" / "identity" / "aliases.json").read_text(encoding="utf-8"))
            links = json.loads((root / "data" / "identity" / "person_links.json").read_text(encoding="utf-8"))

            # Expect 1 person: John Doe
            self.assertEqual(len(people["people"]), 1)

            # Expect 1 alias observed
            self.assertEqual(len(aliases["aliases"]), 1)

            # Expect PersonLink(s) created and unverified.
            self.assertEqual(links.get("schema_version"), 1)
            link_list = links.get("links")
            self.assertIsInstance(link_list, list)
            self.assertGreaterEqual(len(link_list), 1)
            self.assertTrue(all(l.get("verification_state") == "unverified" for l in link_list if isinstance(l, dict)))

    def test_build_creates_distinct_people_when_name_is_ambiguous_within_run(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            run_dir = root / "staging" / "runA"
            clinical_rel = "source/unpacked/clinical/patient.json"
            (run_dir / "source" / "unpacked" / "clinical").mkdir(parents=True, exist_ok=True)

            # Two different patients with the same normalized name in the same run => ambiguity => no auto-merge.
            patient_bundle = {
                "resourceType": "Bundle",
                "entry": [
                    {
                        "resource": {
                            "resourceType": "Patient",
                            "id": "p1",
                            "name": [{"text": "John Doe"}],
                            "identifier": [{"system": "sysA", "value": "111"}],
                        }
                    },
                    {
                        "resource": {
                            "resourceType": "Patient",
                            "id": "p2",
                            "name": [{"text": "Doe, John"}],
                            "identifier": [{"system": "sysB", "value": "222"}],
                        }
                    },
                ],
            }
            _write_json(run_dir / clinical_rel, patient_bundle)
            layout = {"run_id": "runA", "export_xml": "source/unpacked/export.xml", "clinical_json": [clinical_rel]}
            _write_json(run_dir / "layout.json", layout)

            old_cwd = Path.cwd()
            try:
                import os

                os.chdir(root)
                from healthdelta.identity import build_identity

                build_identity(staging_run_dir=str(run_dir))
            finally:
                os.chdir(old_cwd)

            people = json.loads((root / "data" / "identity" / "people.json").read_text(encoding="utf-8"))
            links = json.loads((root / "data" / "identity" / "person_links.json").read_text(encoding="utf-8"))

            self.assertEqual(len(people["people"]), 2)
            person_keys = sorted([p["person_key"] for p in people["people"]])
            self.assertEqual(len(set(person_keys)), 2)

            link_list = links.get("links")
            self.assertIsInstance(link_list, list)
            link_person_keys = sorted([l["person_key"] for l in link_list if isinstance(l, dict) and isinstance(l.get("person_key"), str)])
            self.assertEqual(len(set(link_person_keys)), 2)


if __name__ == "__main__":
    unittest.main()
