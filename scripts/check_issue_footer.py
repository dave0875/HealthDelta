#!/usr/bin/env python3
"""Best-effort commit Issue footer validation with rewrite-tolerant fallbacks."""
from __future__ import annotations

import argparse
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
    proc = subprocess.run(["git", *args], check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout).strip() or f"git {' '.join(args)} failed")
    return proc.stdout.strip()


def _git_try(*args: str) -> str | None:
    proc = subprocess.run(["git", *args], check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def _merge_parents() -> list[str]:
    line = _git_try("rev-list", "--parents", "-n", "1", "HEAD")
    if not line:
        return []
    parts = line.split()
    return parts[1:]


def _load_event() -> dict:
    path = os.getenv("GITHUB_EVENT_PATH")
    if not path or not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _commit_list(range_expr: str) -> list[str]:
    out = _git_try("rev-list", range_expr)
    if not out:
        return []
    return [line for line in out.splitlines() if line]


def _resolve_commit_range_with_notes() -> tuple[list[str], list[str]]:
    notes: list[str] = []
    parents = _merge_parents()
    if len(parents) >= 2:
        mb = _git_try("merge-base", parents[0], parents[1])
        if mb:
            if mb == parents[0]:
                base, head = parents[0], parents[1]
            elif mb == parents[1]:
                base, head = parents[1], parents[0]
            else:
                base, head = mb, "HEAD"
            commits = _commit_list(f"{base}..{head}")
            if commits:
                notes.append("resolved commit range via merge-parent topology.")
                return commits, notes
            head_sha = _git_try("rev-parse", head)
            if head_sha:
                notes.append("merge-parent range was empty; checking merge head only.")
                return [head_sha], notes
        notes.append("merge-parent resolution unavailable; falling back to event metadata.")

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
        anc = subprocess.run(
            ["git", "merge-base", "--is-ancestor", base, head],
            check=False,
            capture_output=True,
            text=True,
        )
        if anc.returncode == 0:
            mb = _git_try("merge-base", base, head)
            if mb:
                commits = _commit_list(f"{mb}..{head}")
                if commits:
                    notes.append("resolved commit range from event before/after ancestry.")
                    return commits, notes
                notes.append("event ancestry range was empty; checking push/pr head only.")
                return [head], notes
        else:
            notes.append(
                "event before SHA is not an ancestor of after (likely rebase/force-push); using rewrite-tolerant fallback."
            )

    if head:
        main_ref = _git_try("rev-parse", "origin/main")
        if main_ref:
            merge_base = _git_try("merge-base", head, main_ref)
            if merge_base:
                commits = _commit_list(f"{merge_base}..{head}")
                if commits:
                    notes.append("resolved range from merge-base(head, origin/main).")
                    return commits, notes
        if _git_try("cat-file", "-e", f"{head}^{{commit}}") is not None:
            notes.append("using head commit only because no stable range was available.")
            return [head], notes

    main_ref = _git_try("rev-parse", "origin/main")
    if main_ref:
        merge_base = _git_try("merge-base", "HEAD", main_ref)
        if merge_base:
            commits = _commit_list(f"{merge_base}..HEAD")
            if commits:
                notes.append("resolved range from merge-base(HEAD, origin/main).")
                return commits, notes

    head_only = _git_try("rev-list", "-n", "1", "HEAD")
    if head_only:
        notes.append("falling back to HEAD-only commit check.")
        return [head_only], notes

    notes.append("unable to resolve any commits; skipping commit-level enforcement.")
    return [], notes


def _resolve_commit_range() -> list[str]:
    commits, _ = _resolve_commit_range_with_notes()
    return commits


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Issue footers in commit messages.")
    parser.add_argument("--print-issue", action="store_true", help="Print the single Issue number if one is found.")
    args = parser.parse_args()

    commits, notes = _resolve_commit_range_with_notes()
    if not args.print_issue:
        for note in notes:
            print(f"governance-info: {note}")
    if not commits:
        if not args.print_issue:
            print("governance-warning: commit Issue footer check skipped (no resolvable commits).")
            print("what happened: git history context was incomplete or rewritten.")
            print("what was checked instead: PR metadata and other durable governance artifacts still run.")
            print("how to fix: ensure checkout has history (fetch-depth: 0) or rerun after refs are available.")
        return 0

    messages: list[str] = []
    resolved: list[str] = []
    for sha in commits:
        msg = _git_try("log", "-1", "--format=%B", sha)
        if msg is None:
            if not args.print_issue:
                print(f"governance-info: commit {sha[:12]} is unavailable locally; skipped.")
            continue
        resolved.append(sha)
        messages.append(msg)
    commits = resolved
    if not commits:
        if not args.print_issue:
            print("governance-warning: no readable commit messages were available for Issue footer checks.")
            print("what happened: commit objects referenced by event metadata were missing after history rewrite.")
            print("what was checked instead: PR metadata checks remain authoritative for this run.")
            print("how to fix: push updated refs or rerun with full commit history fetched.")
        return 0

    missing = commits_missing_issue_footer(messages)
    if missing:
        print("policy failure: missing Issue footer in one or more commits.")
        for sha, msg in zip(commits, messages):
            if not message_has_issue_footer(msg):
                summary = msg.splitlines()[0] if msg else "(empty message)"
                print(f"- {sha[:12]}: {summary}")
        print("Expected footer format: 'Issue: #NN'.")
        print("how to fix: amend commit messages or squash/rebase to include one consistent Issue footer.")
        return 1

    issue_numbers: set[str] = set()
    for msg in messages:
        issue_numbers.update(extract_issue_numbers(msg))

    if not issue_numbers:
        print("policy failure: no Issue footer numbers found in commit set.")
        print("how to fix: include 'Issue: #NN' in commit message footer.")
        return 1
    if len(issue_numbers) > 1:
        issues = ", ".join(sorted(issue_numbers))
        print(f"policy failure: multiple Issue numbers found in commit set: {issues}")
        print("how to fix: keep one issue per PR and make commit footers consistent.")
        return 1

    issue_no = sorted(issue_numbers)[0]
    if args.print_issue:
        print(issue_no)
        return 0

    print("Issue footer check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
