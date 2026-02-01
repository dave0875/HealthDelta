# Session 12 — 2026-02-01

Issue: #117

Goal
- Enforce managed issue worktree location and automate stale worktree pruning.

Notes
- Added `scripts/worktree_manager.py` with `create`, `prune`, and `check` commands.
- Added `healthdelta/worktree_policy.py` for deterministic path policy and prune candidate selection logic.
- Added CI guardrail step to fail when legacy sibling worktree paths are used.
- Added `docs/runbook_worktree.md` and `tests/test_worktree_policy.py`.

Local verification
- python3 -m unittest tests/test_worktree_policy.py -v
- TZ=UTC python3 -m unittest discover -s tests -v
- python3 scripts/worktree_manager.py check
