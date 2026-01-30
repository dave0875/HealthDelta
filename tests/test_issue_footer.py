import importlib.util
from pathlib import Path


def _load_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "check_issue_footer.py"
    spec = importlib.util.spec_from_file_location("check_issue_footer", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_issue_footer_present():
    mod = _load_module()
    msg = "Add feature X\n\nIssue: #72\n"
    assert mod.message_has_issue_footer(msg)


def test_issue_footer_absent():
    mod = _load_module()
    msg = "Add feature X\n\nRefs #72\n"
    assert not mod.message_has_issue_footer(msg)


def test_issue_footer_allows_trailing_space():
    mod = _load_module()
    msg = "Fix bug\n\nIssue: #123   \n"
    assert mod.message_has_issue_footer(msg)
