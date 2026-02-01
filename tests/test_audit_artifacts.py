import importlib.util
from pathlib import Path


def _load_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "check_audit_artifacts.py"
    spec = importlib.util.spec_from_file_location("check_audit_artifacts", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_select_single_issue():
    mod = _load_module()
    msgs = ["Change\n\nIssue: #72\n", "Other\n\nIssue: #72\n"]
    assert mod.select_single_issue(msgs) == "72"


def test_select_single_issue_rejects_multiple():
    mod = _load_module()
    msgs = ["Issue: #72\n", "Issue: #73\n"]
    assert mod.select_single_issue(msgs) is None


def test_has_non_ai_changes():
    mod = _load_module()
    assert mod.has_non_ai_changes([".ai/time/time.csv"]) is False
    assert mod.has_non_ai_changes(["docs/plan.md"]) is True


def test_time_csv_has_issue(tmp_path: Path):
    mod = _load_module()
    p = tmp_path / "time.csv"
    p.write_text("2026-01-30,72,,5,codex,,note\n", encoding="utf-8")
    assert mod.time_csv_has_issue(p, "72") is True
    assert mod.time_csv_has_issue(p, "73") is False
