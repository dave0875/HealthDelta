from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


def managed_root(repo_root: Path, configured_root: str | None = None) -> Path:
    if configured_root:
        return Path(configured_root).expanduser().resolve()
    # Default: keep issue worktrees out of ~/Code clutter.
    return (repo_root.parent / ".worktrees" / repo_root.name).resolve()


def issue_branch(issue_no: int) -> str:
    return f"issue-{issue_no}"


def issue_worktree_path(root: Path, issue_no: int) -> Path:
    return root / issue_branch(issue_no)


@dataclass(frozen=True)
class WorktreeRef:
    path: Path
    branch: str | None


def parse_worktree_porcelain(text: str) -> list[WorktreeRef]:
    out: list[WorktreeRef] = []
    path: Path | None = None
    branch: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("worktree "):
            if path is not None:
                out.append(WorktreeRef(path=path, branch=branch))
            path = Path(line.split(" ", 1)[1])
            branch = None
            continue
        if line.startswith("branch "):
            ref = line.split(" ", 1)[1]
            branch = ref.removeprefix("refs/heads/")
    if path is not None:
        out.append(WorktreeRef(path=path, branch=branch))
    return out


def is_legacy_issue_sibling(path: Path, repo_root: Path) -> bool:
    name = path.name
    if not name.startswith(f"{repo_root.name}-issue"):
        return False
    return path.parent == repo_root.parent


def issue_no_from_branch(branch: str | None) -> int | None:
    if not isinstance(branch, str):
        return None
    if not branch.startswith("issue-"):
        return None
    suffix = branch.split("-", 1)[1]
    return int(suffix) if suffix.isdigit() else None


def select_prune_candidates(
    *,
    worktrees: list[WorktreeRef],
    repo_root: Path,
    root: Path,
    closed_issues: set[int],
    merged_branches: set[str],
) -> list[WorktreeRef]:
    candidates: list[WorktreeRef] = []
    for wt in worktrees:
        if wt.path == repo_root:
            continue
        if not str(wt.path).startswith(str(root)):
            continue
        issue_no = issue_no_from_branch(wt.branch)
        if issue_no is None:
            continue
        if issue_no in closed_issues and wt.branch in merged_branches:
            candidates.append(wt)
    return sorted(candidates, key=lambda x: str(x.path))
