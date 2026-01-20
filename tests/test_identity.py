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
    def test_build_links_name_variants_and_preserves_external_ids(self) -> None:
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
                            "name": [{"text": "Doe, John"}],
                            "identifier": [{"system": "sysA", "value": "111"}],
                        }
                    },
                    {
                        "resource": {
                            "resourceType": "Patient",
                            "id": "p2",
                            "name": [{"text": "John Doe"}],
                            "identifier": [{"system": "sysB", "value": "222"}],
                        }
                    },
                    {
                        "resource": {
                            "resourceType": "Patient",
                            "id": "p3",
                            "name": [{"text": "Jane Doe"}],
                            "identifier": [{"system": "sysC", "value": "333"}],
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

            # Expect 2 people: John Doe and Jane Doe
            self.assertEqual(len(people["people"]), 2)

            # Expect 3 aliases observed
            self.assertEqual(len(aliases["aliases"]), 3)

            # Verify the two John variants map to the same person_key
            john_aliases = [a for a in aliases["aliases"] if a["first_norm"] == "john" and a["last_norm"] == "doe"]
            self.assertEqual(len(john_aliases), 2)
            self.assertEqual(john_aliases[0]["person_key"], john_aliases[1]["person_key"])

            # Verify external ids are preserved and distinct
            ext_sets = [tuple((e["system"], e["value"]) for e in a["source"]["external_ids"]) for a in john_aliases]
            self.assertNotEqual(ext_sets[0], ext_sets[1])


if __name__ == "__main__":
    unittest.main()

