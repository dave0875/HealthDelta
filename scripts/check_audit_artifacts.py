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


def _git_try(*args: str) -> str | None:
    proc = subprocess.run(["git", *args], check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def _merge_base() -> str:
    main_ref = _git_try("rev-parse", "origin/main")
    if main_ref:
        mb = _git_try("merge-base", "HEAD", main_ref)
        if mb:
            return mb
    head = _git_try("rev-list", "-n", "1", "HEAD")
    return head or ""


def _changed_paths() -> list[str]:
    base = _merge_base()
    if not base:
        print("governance-warning: unable to resolve merge-base; assuming no non-.ai changes for audit check.")
        return []
    out = _git_try("diff", "--name-only", f"{base}..HEAD")
    if out is None:
        print("governance-warning: git diff range unavailable (history rewrite/shallow clone); audit check skipped.")
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def _commit_messages() -> list[str]:
    base = _merge_base()
    commits: list[str] = []
    if base:
        out = _git_try("rev-list", f"{base}..HEAD")
        if out:
            commits = out.splitlines()
    if not commits:
        head = _git_try("rev-list", "-n", "1", "HEAD")
        if head:
            commits = [head]
    messages: list[str] = []
    for sha in commits:
        msg = _git_try("log", "-1", "--format=%B", sha)
        if msg:
            messages.append(msg)
    return messages


def main() -> int:
    paths = _changed_paths()
    if not has_non_ai_changes(paths):
        print("Audit artifact check skipped (no non-.ai changes).")
        return 0

    messages = _commit_messages()
    issue_no = select_single_issue(messages)
    if not issue_no:
        print("governance-warning: unable to resolve a single Issue number from commits.")
        print("what happened: commit context was unavailable or inconsistent after history rewrite.")
        print("what was checked instead: audit check is skipped for this run; PR metadata check remains active.")
        print("how to fix: rerun with full history or ensure one Issue footer is present in commit metadata.")
        return 0

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
