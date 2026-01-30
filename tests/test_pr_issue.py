import importlib.util
from pathlib import Path


def _load_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "check_pr_issue.py"
    spec = importlib.util.spec_from_file_location("check_pr_issue", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_extract_issue_numbers_from_title_and_body():
    mod = _load_module()
    text = "Title\n\nIssue: #72\nBody Issue: #73"
    assert mod.extract_issue_numbers(text) == {"72", "73"}
