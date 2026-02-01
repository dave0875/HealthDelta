import importlib.util
import os
import subprocess
import unittest
from pathlib import Path
from unittest import mock


def _load_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "check_issue_footer.py"
    spec = importlib.util.spec_from_file_location("check_issue_footer", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class TestIssueFooter(unittest.TestCase):
    def test_issue_footer_present(self):
        mod = _load_module()
        msg = "Add feature X\n\nIssue: #72\n"
        self.assertTrue(mod.message_has_issue_footer(msg))

    def test_issue_footer_absent(self):
        mod = _load_module()
        msg = "Add feature X\n\nRefs #72\n"
        self.assertFalse(mod.message_has_issue_footer(msg))

    def test_issue_footer_allows_trailing_space(self):
        mod = _load_module()
        msg = "Fix bug\n\nIssue: #123   \n"
        self.assertTrue(mod.message_has_issue_footer(msg))


class TestResolveCommitRange(unittest.TestCase):
    def test_force_push_fallback(self):
        mod = _load_module()

        def fake_git(*args):
            if args == ("rev-list", "--parents", "-n", "1", "HEAD"):
                return "head parent"
            if args == ("rev-parse", "origin/main"):
                return "mainsha"
            if args == ("merge-base", "headsha", "mainsha"):
                return "basesha"
            if args == ("rev-list", "basesha..headsha"):
                return "c1\nc2"
            raise AssertionError(f"Unexpected git call: {args}")

        with mock.patch.dict(os.environ, {"GITHUB_EVENT_NAME": "push"}):
            with mock.patch.object(
                mod, "_load_event", return_value={"before": "badbase", "after": "headsha"}
            ):
                with mock.patch.object(mod, "_git", side_effect=fake_git):
                    with mock.patch.object(
                        mod.subprocess,
                        "check_call",
                        side_effect=subprocess.CalledProcessError(1, ["git"]),
                    ):
                        commits = mod._resolve_commit_range()

        self.assertEqual(commits, ["c1", "c2"])

    def test_push_ancestor(self):
        mod = _load_module()

        def fake_git(*args):
            if args == ("rev-list", "--parents", "-n", "1", "HEAD"):
                return "head parent"
            if args == ("merge-base", "basesha", "headsha"):
                return "basesha"
            if args == ("rev-list", "basesha..headsha"):
                return "c3\nc4"
            raise AssertionError(f"Unexpected git call: {args}")

        with mock.patch.dict(os.environ, {"GITHUB_EVENT_NAME": "push"}):
            with mock.patch.object(
                mod, "_load_event", return_value={"before": "basesha", "after": "headsha"}
            ):
                with mock.patch.object(mod, "_git", side_effect=fake_git):
                    with mock.patch.object(mod.subprocess, "check_call", return_value=None):
                        commits = mod._resolve_commit_range()

        self.assertEqual(commits, ["c3", "c4"])


if __name__ == "__main__":
    unittest.main()
