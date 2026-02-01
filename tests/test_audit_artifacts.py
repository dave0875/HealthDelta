import importlib.util
import os
import unittest
from pathlib import Path


def _load_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "check_audit_artifacts.py"
    spec = importlib.util.spec_from_file_location("check_audit_artifacts", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class TestAuditArtifacts(unittest.TestCase):
    def test_select_single_issue(self) -> None:
        mod = _load_module()
        msgs = ["Change\n\nIssue: #72\n", "Other\n\nIssue: #72\n"]
        self.assertEqual(mod.select_single_issue(msgs), "72")

    def test_select_single_issue_rejects_multiple(self) -> None:
        mod = _load_module()
        msgs = ["Issue: #72\n", "Issue: #73\n"]
        self.assertIsNone(mod.select_single_issue(msgs))

    def test_has_non_ai_changes(self) -> None:
        mod = _load_module()
        self.assertFalse(mod.has_non_ai_changes([".ai/time/time.csv"]))
        self.assertTrue(mod.has_non_ai_changes(["docs/plan.md"]))

    def test_time_csv_has_issue(self) -> None:
        mod = _load_module()
        with self.subTest("match"):
            with self.subTest("temp"):
                p = Path(self._tmp_dir()) / "time.csv"
                p.write_text("2026-01-30,72,,5,codex,,note\n", encoding="utf-8")
                self.assertTrue(mod.time_csv_has_issue(p, "72"))
                self.assertFalse(mod.time_csv_has_issue(p, "73"))

    def test_time_csv_updated(self) -> None:
        mod = _load_module()
        self.assertTrue(mod.time_csv_updated([".ai/time/time.csv"]))
        self.assertFalse(mod.time_csv_updated(["docs/plan.md"]))

    def test_updated_session_paths_and_issue(self) -> None:
        mod = _load_module()
        root = Path(self._tmp_dir())
        p = root / ".ai" / "sessions" / "2026-02-01" / "session_1.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# Session\n\nIssue: #86\n", encoding="utf-8")

        rel = p.relative_to(root).as_posix()
        paths = [rel, "docs/plan.md"]
        session_paths = mod.updated_session_paths(paths)
        self.assertEqual(session_paths, [Path(rel)])

        old_cwd = Path.cwd()
        try:
            os.chdir(root)
            self.assertTrue(mod.session_paths_have_issue(session_paths, "86"))
            self.assertFalse(mod.session_paths_have_issue(session_paths, "85"))
        finally:
            os.chdir(old_cwd)

    def _tmp_dir(self) -> str:
        import tempfile

        if not hasattr(self, "_td"):
            self._td = tempfile.TemporaryDirectory()
            self.addCleanup(self._td.cleanup)
        return self._td.name


if __name__ == "__main__":
    unittest.main()
