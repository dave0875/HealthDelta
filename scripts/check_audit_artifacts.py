#!/usr/bin/env python3
"""Fail CI if required audit artifacts are missing for non-.ai changes."""
from __future__ import annotations

import csv
import os
import re
import subprocess
import sys
from pathlib import Path

ISSUE_NUMBER_RE = re.compile(r"Issue:\s*#(\d+)\s*$", re.MULTILINE)
SESSION_PATH_RE = re.compile(r"^\.ai/sessions/\d{4}-\d{2}-\d{2}/session_\d+\.md$")


def extract_issue_numbers(message: str) -> list[str]:
    return ISSUE_NUMBER_RE.findall(message or "")


def select_single_issue(messages: list[str]) -> str | None:
    issues: set[str] = set()
    for msg in messages:
        issues.update(extract_issue_numbers(msg))
    if len(issues) != 1:
        return None
    return sorted(issues)[0]


def has_non_ai_changes(paths: list[str]) -> bool:
    return any(p and not p.startswith(".ai/") for p in paths)


def time_csv_has_issue(path: Path, issue_no: str) -> bool:
    if not path.exists():
        return False
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        for row in reader:
            if len(row) >= 2 and row[1].strip() == issue_no:
                return True
    return False


def time_csv_updated(paths: list[str]) -> bool:
    return ".ai/time/time.csv" in paths


def updated_session_paths(paths: list[str]) -> list[Path]:
    out: list[Path] = []
    for p in paths:
        if SESSION_PATH_RE.match(p):
            out.append(Path(p))
    return out


def session_paths_have_issue(paths: list[Path], issue_no: str) -> bool:
    marker = f"Issue: #{issue_no}"
    for p in paths:
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        if marker in text:
            return True
    return False


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def _merge_base() -> str:
    try:
        main_ref = _git("rev-parse", "origin/main")
        return _git("merge-base", "HEAD", main_ref)
    except Exception:
        return _git("rev-list", "-n", "1", "HEAD")


def _changed_paths() -> list[str]:
    base = _merge_base()
    out = _git("diff", "--name-only", f"{base}..HEAD")
    return [line.strip() for line in out.splitlines() if line.strip()]


def _commit_messages() -> list[str]:
    base = _merge_base()
    commits = _git("rev-list", f"{base}..HEAD").splitlines()
    if not commits:
        commits = [_git("rev-list", "-n", "1", "HEAD")]
    return [_git("log", "-1", "--format=%B", sha) for sha in commits]


def main() -> int:
    paths = _changed_paths()
    if not has_non_ai_changes(paths):
        print("Audit artifact check skipped (no non-.ai changes).")
        return 0

    messages = _commit_messages()
    issue_no = select_single_issue(messages)
    if not issue_no:
        print("Unable to resolve a single Issue number from commits.")
        return 1

    prompt_path = Path(".ai") / "prompts" / f"issue_{issue_no}.md"
    if not prompt_path.exists():
        print(f"Missing prompt file: {prompt_path}")
        return 1

    if not time_csv_updated(paths):
        print("Missing required file update for code changes: .ai/time/time.csv")
        return 1

    session_paths = updated_session_paths(paths)
    if not session_paths:
        print("Missing required session update for code changes under .ai/sessions/YYYY-MM-DD/session_N.md")
        return 1

    time_csv = Path(".ai") / "time" / "time.csv"
    if not time_csv_has_issue(time_csv, issue_no):
        print(f"Missing time.csv entry for Issue #{issue_no}")
        return 1

    if not session_paths_have_issue(session_paths, issue_no):
        print(f"No updated session entry references Issue #{issue_no}")
        return 1

    print("Audit artifact check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
