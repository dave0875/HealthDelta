#!/usr/bin/env python3
"""Managed issue-worktree lifecycle (create/prune/policy-check)."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from healthdelta.worktree_policy import (
    is_legacy_issue_sibling,
    issue_branch,
    issue_no_from_branch,
    issue_worktree_path,
    managed_root,
    parse_worktree_porcelain,
    select_prune_candidates,
)


def _run(repo_root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=check,
        capture_output=True,
        text=True,
    )


def _git_output(repo_root: Path, *args: str) -> str:
    return _run(repo_root, *args).stdout.strip()


def _worktrees(repo_root: Path):
    text = _git_output(repo_root, "worktree", "list", "--porcelain")
    return parse_worktree_porcelain(text)


def _issue_is_closed(repo: str, issue_no: int) -> bool:
    p = subprocess.run(
        ["gh", "issue", "view", str(issue_no), "--repo", repo, "--json", "state", "--jq", ".state"],
        check=False,
        capture_output=True,
        text=True,
    )
    return p.returncode == 0 and p.stdout.strip().upper() == "CLOSED"


def _branch_merged(repo_root: Path, branch: str) -> bool:
    p = _run(repo_root, "merge-base", "--is-ancestor", branch, "origin/main", check=False)
    return p.returncode == 0


def cmd_create(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    root = managed_root(repo_root, args.root)
    root.mkdir(parents=True, exist_ok=True)

    _run(repo_root, "fetch", "origin")
    if not args.no_auto_prune:
        _prune(repo_root=repo_root, root=root, repo=args.repo)
    branch = issue_branch(args.issue)
    target = issue_worktree_path(root, args.issue)
    if target.exists():
        print(f"exists: {target}")
        return 0

    has_branch = _run(repo_root, "rev-parse", "--verify", f"refs/heads/{branch}", check=False).returncode == 0
    if has_branch:
        _run(repo_root, "worktree", "add", str(target), branch)
    else:
        _run(repo_root, "worktree", "add", "-b", branch, str(target), "origin/main")
    print(str(target))
    return 0


def _prune(*, repo_root: Path, root: Path, repo: str) -> int:
    if not root.exists():
        return 0

    _run(repo_root, "fetch", "origin")
    refs = _worktrees(repo_root)
    issue_nos = sorted({n for n in (issue_no_from_branch(w.branch) for w in refs) if n is not None})
    closed = {n for n in issue_nos if _issue_is_closed(repo, n)}
    merged = {w.branch for w in refs if isinstance(w.branch, str) and _branch_merged(repo_root, w.branch)}
    candidates = select_prune_candidates(
        worktrees=refs,
        repo_root=repo_root,
        root=root,
        closed_issues=closed,
        merged_branches=merged,
    )
    for wt in candidates:
        _run(repo_root, "worktree", "remove", "-f", str(wt.path))
        print(f"pruned {wt.path}")
    _run(repo_root, "worktree", "prune")
    return 0


def cmd_prune(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    root = managed_root(repo_root, args.root)
    rc = _prune(repo_root=repo_root, root=root, repo=args.repo)
    if not root.exists():
        print("nothing to prune")
    else:
        print("prune complete")
    return rc


def cmd_check(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    root = managed_root(repo_root, args.root)
    refs = _worktrees(repo_root)
    errors: list[str] = []
    for wt in refs:
        if wt.path == repo_root:
            continue
        if is_legacy_issue_sibling(wt.path, repo_root):
            errors.append(f"legacy sibling worktree path is disallowed: {wt.path}")
        issue_no = issue_no_from_branch(wt.branch)
        if issue_no is not None and not str(wt.path).startswith(str(root)):
            errors.append(f"issue worktree must live under {root}: {wt.path}")
    if errors:
        for e in errors:
            print(e)
        return 1
    print("worktree policy check passed")
    return 0


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Manage issue worktrees in a hidden root.")
    p.add_argument("--repo-root", default=os.getcwd(), help="Repository root (default: cwd).")
    p.add_argument("--root", default=os.getenv("HEALTHDELTA_WORKTREE_ROOT"), help="Managed worktree root path.")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("create", help="Create issue worktree under managed root.")
    c.add_argument("--issue", required=True, type=int)
    c.add_argument("--repo", default="dave0875/HealthDelta", help="GitHub repo for issue state lookup when auto-pruning.")
    c.add_argument("--no-auto-prune", action="store_true", help="Skip auto-prune before creating worktree.")
    c.set_defaults(fn=cmd_create)

    pr = sub.add_parser("prune", help="Prune closed+merged issue worktrees under managed root.")
    pr.add_argument("--repo", default="dave0875/HealthDelta", help="GitHub repo for issue state lookup.")
    pr.set_defaults(fn=cmd_prune)

    ck = sub.add_parser("check", help="Enforce worktree path policy.")
    ck.set_defaults(fn=cmd_check)
    return p


def main() -> int:
    args = _parser().parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
