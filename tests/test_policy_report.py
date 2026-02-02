import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


def _load_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "render_policy_report.py"
    spec = importlib.util.spec_from_file_location("render_policy_report", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class TestPolicyReport(unittest.TestCase):
    def test_build_report_marks_failure(self) -> None:
        mod = _load_module()
        report = mod.build_report(
            {
                "POLICY_ISSUE_FOOTER": "success",
                "POLICY_PR_ISSUE": "failure",
                "POLICY_AUDIT_ARTIFACTS": "success",
                "POLICY_PROMPT_IMMUTABILITY": "success",
                "POLICY_WORKTREE": "success",
            }
        )
        self.assertTrue(report["any_failure"])
        outcomes = {row["check"]: row["outcome"] for row in report["policy_checks"]}
        self.assertEqual(outcomes["policy_pr_issue"], "failure")

    def test_script_writes_json_report(self) -> None:
        mod = _load_module()
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "policy_report.json"
            report = mod.build_report({})
            out.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
            loaded = json.loads(out.read_text(encoding="utf-8"))
            self.assertIn("policy_checks", loaded)
            self.assertIn("any_failure", loaded)


if __name__ == "__main__":
    unittest.main()
