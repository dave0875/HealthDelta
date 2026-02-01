# Runbook: Managed Issue Worktrees

This runbook defines the enforced worktree lifecycle for issue-scoped development.

## Why

- Keep `~/Code` clean (no `HealthDelta-issue##` sibling directories).
- Preserve isolated issue branches/workspaces.
- Prune stale worktrees automatically when issue + merge lifecycle is complete.

## Managed location

Default root:

- `<repo-parent>/.worktrees/<repo-name>/`
- Example for this repo: `~/Code/.worktrees/HealthDelta/`

Override root (optional):

- `HEALTHDELTA_WORKTREE_ROOT=/path/to/root`

## Commands

From repo root:

```bash
python3 scripts/worktree_manager.py create --issue 117
python3 scripts/worktree_manager.py prune
python3 scripts/worktree_manager.py check
```

### Behavior

- `create`
  - auto-prunes first (unless `--no-auto-prune`)
  - creates or reuses branch `issue-N`
  - creates worktree at `<managed-root>/issue-N`
- `prune`
  - removes managed issue worktrees when:
    - GitHub issue is closed, and
    - issue branch is merged into `origin/main`
- `check`
  - fails on legacy sibling pattern: `~/Code/HealthDelta-issue##`
  - fails when issue branches live outside managed root

## CI guardrail

CI runs `python3 scripts/worktree_manager.py check` to enforce path policy.

## Migration

If legacy sibling worktrees exist:

```bash
python3 scripts/worktree_manager.py prune
```

If needed, remove legacy paths manually via:

```bash
git worktree remove -f /path/to/legacy/worktree
git worktree prune
```
