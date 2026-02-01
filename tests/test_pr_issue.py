import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


def _load_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "check_pr_issue.py"
    spec = importlib.util.spec_from_file_location("check_pr_issue", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class TestPrIssueCheck(unittest.TestCase):
    def test_pr_issue_required(self) -> None:
        mod = _load_module()
        with tempfile.TemporaryDirectory() as td:
            event_path = Path(td) / "event.json"
            event_path.write_text('{"pull_request": {"title": "No footer", "body": ""}}', encoding="utf-8")
            with mock.patch.dict(
                os.environ,
                {"GITHUB_EVENT_NAME": "pull_request", "GITHUB_EVENT_PATH": str(event_path)},
                clear=False,
            ):
                with mock.patch("builtins.print"):
                    self.assertEqual(mod.main(), 1)

    def test_commit_resolution_unavailable_is_non_blocking(self) -> None:
        mod = _load_module()
        with tempfile.TemporaryDirectory() as td:
            event_path = Path(td) / "event.json"
            event_path.write_text(
                '{"pull_request": {"title": "Issue: #130", "body": "context"}}', encoding="utf-8"
            )
            with mock.patch.dict(
                os.environ,
                {"GITHUB_EVENT_NAME": "pull_request", "GITHUB_EVENT_PATH": str(event_path)},
                clear=False,
            ):
                with mock.patch.object(mod, "_commit_issue_number", return_value=None):
                    with mock.patch("builtins.print"):
                        self.assertEqual(mod.main(), 0)


if __name__ == "__main__":
    unittest.main()
