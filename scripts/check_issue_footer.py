#!/usr/bin/env python3
"""Fail CI if commits lack an Issue footer (Issue: #NN)."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from typing import Iterable

ISSUE_FOOTER_RE = re.compile(r"^Issue:\s*#\d+\s*$", re.MULTILINE)
ISSUE_NUMBER_RE = re.compile(r"Issue:\s*#(\d+)\s*$", re.MULTILINE)


def message_has_issue_footer(message: str) -> bool:
    return bool(ISSUE_FOOTER_RE.search(message or ""))


def commits_missing_issue_footer(messages: Iterable[str]) -> list[str]:
    missing: list[str] = []
    for msg in messages:
        if not message_has_issue_footer(msg):
            missing.append(msg)
    return missing


def extract_issue_numbers(message: str) -> list[str]:
    return ISSUE_NUMBER_RE.findall(message or "")


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def _merge_parents() -> list[str]:
    line = _git("rev-list", "--parents", "-n", "1", "HEAD")
    parts = line.split()
    return parts[1:]


def _load_event() -> dict:
    path = os.getenv("GITHUB_EVENT_PATH")
    if not path or not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _resolve_commit_range() -> list[str]:
    parents = _merge_parents()
    if len(parents) >= 2:
        mb = _git("merge-base", parents[0], parents[1])
        if mb == parents[0]:
            base, head = parents[0], parents[1]
        elif mb == parents[1]:
            base, head = parents[1], parents[0]
        else:
            base, head = mb, "HEAD"
        commits = _git("rev-list", f"{base}..{head}").splitlines()
        return commits or [head]

    event = _load_event()
    event_name = os.getenv("GITHUB_EVENT_NAME", "")

    base = None
    head = None
    if event_name == "pull_request" and isinstance(event.get("pull_request"), dict):
        base = event["pull_request"].get("base", {}).get("sha")
        head = event["pull_request"].get("head", {}).get("sha")
    elif event_name == "push":
        base = event.get("before")
        head = event.get("after")

    if head and base and base != "0" * 40:
        try:
            subprocess.check_call(["git", "merge-base", "--is-ancestor", base, head])
            mb = _git("merge-base", base, head)
            commits = _git("rev-list", f"{mb}..{head}").splitlines()
            return commits or [head]
        except Exception:
            pass

        try:
            main_ref = _git("rev-parse", "origin/main")
            merge_base = _git("merge-base", head, main_ref)
            commits = _git("rev-list", f"{merge_base}..{head}").splitlines()
            return commits or [head]
        except Exception:
            commits = _git("rev-list", f"{base}..{head}").splitlines()
            return commits or [head]

    try:
        main_ref = _git("rev-parse", "origin/main")
        merge_base = _git("merge-base", "HEAD", main_ref)
        commits = _git("rev-list", f"{merge_base}..HEAD").splitlines()
        return commits or [merge_base]
    except Exception:
        pass

    return _git("rev-list", "-n", "1", "HEAD").splitlines()


def main() -> int:
    commits = _resolve_commit_range()
    if not commits:
        print("No commits resolved for issue footer check.")
        return 1

    messages = [_git("log", "-1", "--format=%B", sha) for sha in commits]
    missing = commits_missing_issue_footer(messages)
    if missing:
        print("Missing Issue footer in one or more commits.")
        for sha, msg in zip(commits, messages):
            if not message_has_issue_footer(msg):
                summary = msg.splitlines()[0] if msg else "(empty message)"
                print(f"- {sha[:12]}: {summary}")
        print("Expected footer format: 'Issue: #NN'.")
        return 1

    issue_numbers: set[str] = set()
    for msg in messages:
        issue_numbers.update(extract_issue_numbers(msg))

    if not issue_numbers:
        print("No Issue footer numbers found in commit set.")
        return 1
    if len(issue_numbers) > 1:
        issues = ", ".join(sorted(issue_numbers))
        print(f"Multiple Issue numbers found in commit set: {issues}")
        return 1

    print("Issue footer check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
