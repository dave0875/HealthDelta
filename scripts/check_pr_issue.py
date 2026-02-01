#!/usr/bin/env python3
"""Fail CI if PR metadata lacks Issue footer matching commit Issue."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

ISSUE_NUMBER_RE = re.compile(r"Issue:\s*#(\d+)\s*", re.MULTILINE)


def extract_issue_numbers(text: str) -> set[str]:
    return set(ISSUE_NUMBER_RE.findall(text or ""))


def _load_event() -> dict:
    path = os.getenv("GITHUB_EVENT_PATH")
    if not path or not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _commit_issue_number() -> str | None:
    try:
        out = subprocess.check_output(
            [sys.executable, "scripts/check_issue_footer.py", "--print-issue"],
            text=True,
        ).strip()
    except subprocess.CalledProcessError:
        return None
    return out or None


def main() -> int:
    if os.getenv("GITHUB_EVENT_NAME") != "pull_request":
        print("PR issue check skipped (not a pull_request event).")
        return 0

    event = _load_event()
    pr = event.get("pull_request") if isinstance(event, dict) else None
    if not isinstance(pr, dict):
        print("Missing pull_request payload; cannot validate PR issue metadata.")
        return 1

    title = pr.get("title") if isinstance(pr.get("title"), str) else ""
    body = pr.get("body") if isinstance(pr.get("body"), str) else ""
    pr_issues = extract_issue_numbers("\n".join([title, body]))

    if not pr_issues:
        print("PR title/body must include Issue: #NN.")
        return 1

    issue_no = _commit_issue_number()
    if not issue_no:
        print("Unable to resolve commit Issue number.")
        return 1

    if issue_no not in pr_issues:
        issues = ", ".join(sorted(pr_issues))
        print(f"PR Issue numbers ({issues}) do not match commit Issue #{issue_no}.")
        return 1

    print("PR Issue metadata check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
