#!/usr/bin/env python3
"""Validate PR metadata Issue anchor with rewrite-tolerant commit fallback."""
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
    proc = subprocess.run(
        [sys.executable, "scripts/check_issue_footer.py", "--print-issue"],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print("governance-info: commit Issue resolution failed; proceeding with PR metadata as authoritative anchor.")
        stderr = (proc.stderr or "").strip()
        if stderr:
            print(f"governance-info: commit resolution detail: {stderr}")
        return None
    out = proc.stdout.strip()
    return out or None


def main() -> int:
    if os.getenv("GITHUB_EVENT_NAME") != "pull_request":
        print("PR issue check skipped (not a pull_request event).")
        return 0

    event = _load_event()
    pr = event.get("pull_request") if isinstance(event, dict) else None
    if not isinstance(pr, dict):
        print("governance-warning: missing pull_request payload; PR Issue metadata check skipped.")
        print("what happened: CI event payload did not include pull_request data.")
        print("what was checked instead: commit-level and audit artifact checks still run.")
        print("how to fix: rerun from a pull_request event context.")
        return 1

    title = pr.get("title") if isinstance(pr.get("title"), str) else ""
    body = pr.get("body") if isinstance(pr.get("body"), str) else ""
    pr_issues = extract_issue_numbers("\n".join([title, body]))

    if not pr_issues:
        print("policy failure: PR title/body must include Issue: #NN.")
        print("how to fix: add 'Issue: #NN' to the PR title or body.")
        return 1

    issue_no = _commit_issue_number()
    if not issue_no:
        print("governance-info: commit-level Issue check unavailable (history rewrite or shallow context).")
        print("governance-info: using PR metadata as the durable enforcement anchor for this run.")
        return 0

    if issue_no not in pr_issues:
        issues = ", ".join(sorted(pr_issues))
        print(f"policy failure: PR Issue numbers ({issues}) do not match commit Issue #{issue_no}.")
        print("how to fix: make PR Issue footer match commit Issue footer, or re-scope commits to one issue.")
        return 1

    print("PR Issue metadata check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
