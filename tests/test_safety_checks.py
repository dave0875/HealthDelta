import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


def _load_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "check_safety_outputs.py"
    spec = importlib.util.spec_from_file_location("check_safety_outputs", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class TestSafetyChecks(unittest.TestCase):
    def test_run_safety_check_passes_for_fixture(self) -> None:
        mod = _load_module()
        with tempfile.TemporaryDirectory() as td:
            report = mod.run_safety_check(
                input_path="tests/fixtures/profile_export",
                work_dir=str(Path(td) / "work"),
            )
            self.assertTrue(report["ok"], msg=json.dumps(report, sort_keys=True))
            self.assertEqual(report["errors"], [])

    def test_validate_qa_requires_insufficiency_message_on_abstain(self) -> None:
        mod = _load_module()
        errors: list[str] = []
        mod._validate_qa(
            {
                "qa": {
                    "abstained": True,
                    "answer": "No data.",
                    "disclaimer": "not medical advice",
                    "citations": [],
                }
            },
            errors,
        )
        self.assertIn("qa.abstained without insufficiency message", errors)


if __name__ == "__main__":
    unittest.main()
