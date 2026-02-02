from pathlib import Path
import unittest


class TestCIPolicyConfig(unittest.TestCase):
    def test_ci_workflow_has_issue_reference_gate(self) -> None:
        ci = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        self.assertIn("Enforce Issue footer in commit messages", ci)
        self.assertIn("python3 scripts/check_issue_footer.py", ci)
        self.assertIn("Enforce PR Issue metadata", ci)
        self.assertIn("python3 scripts/check_pr_issue.py", ci)

    def test_ci_policy_failure_step_is_blocking(self) -> None:
        ci = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        self.assertIn("Fail if policy or unittest failed", ci)
        self.assertIn("policy failure: one or more governance checks failed.", ci)


if __name__ == "__main__":
    unittest.main()
