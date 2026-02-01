---
Story
As a maintainer,
I want issue-scoped worktrees to be created in a dedicated hidden workspace with automatic pruning,
So that local workflows stay clean while preserving isolated branch safety.

Context / Why
Issue-scoped worktrees currently appear as sibling folders in `~/Code`, causing clutter and confusion. The method should be enforced by infrastructure code, not informal process notes, and should automatically clean stale/merged worktrees.

Acceptance Criteria
- A repo-managed script creates issue worktrees under a dedicated hidden root (not sibling `HealthDelta-issue##` folders).
- A repo-managed prune command removes merged/closed issue worktrees automatically.
- A CI/local guardrail fails when prohibited sibling worktree paths are used by the managed workflow metadata.
- Runbook docs describe deterministic usage and cleanup commands.
- Tests validate path derivation, create/prune selection logic, and policy checks.

Out of Scope
- Managing arbitrary non-issue worktrees outside the managed workflow.

Notes
- This is governance + developer-experience infrastructure; AGENTS.md may reference the workflow but must not be the source of enforcement.
---
