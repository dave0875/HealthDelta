#!/usr/bin/env python3
"""Fail CI if existing issue prompt files are modified."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ISSUE_PROMPT_RE = re.compile(r"^\.ai/prompts/issue_(\d+)\.md$")
FOLLOWUP_PROMPT_RE = re.compile(r"^\.ai/prompts/issue_(\d+)_followup_([1-9])\.md$")


def is_issue_prompt(path: str) -> bool:
    return bool(ISSUE_PROMPT_RE.match(path))


def is_followup_prompt(path: str) -> bool:
    return bool(FOLLOWUP_PROMPT_RE.match(path))


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def _merge_base() -> str:
    try:
        main_ref = _git("rev-parse", "origin/main")
        return _git("merge-base", "HEAD", main_ref)
    except Exception:
        return _git("rev-list", "-n", "1", "HEAD")


def _changed_paths() -> list[tuple[str, str]]:
    base = _merge_base()
    out = _git("diff", "--name-status", f"{base}..HEAD")
    changes: list[tuple[str, str]] = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            changes.append((parts[0], parts[1]))
    return changes


def main() -> int:
    violations: list[str] = []
    for status, path in _changed_paths():
        if not is_issue_prompt(path):
            continue
        if is_followup_prompt(path):
            continue
        if status != "A":
            violations.append(path)

    if violations:
        for path in violations:
            print(f"Prompt immutability violation: {path}")
        return 1

    print("Prompt immutability check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
