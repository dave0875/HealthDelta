import importlib.util
from pathlib import Path


def _load_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "check_prompt_immutability.py"
    spec = importlib.util.spec_from_file_location("check_prompt_immutability", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_prompt_path_matching():
    mod = _load_module()
    assert mod.is_issue_prompt(".ai/prompts/issue_72.md") is True
    assert mod.is_followup_prompt(".ai/prompts/issue_72_followup_1.md") is True
    assert mod.is_followup_prompt(".ai/prompts/issue_72_followup_9.md") is True
    assert mod.is_followup_prompt(".ai/prompts/issue_72_followup_10.md") is False
    assert mod.is_issue_prompt(".ai/prompts/issue_72_followup_1.md") is False
