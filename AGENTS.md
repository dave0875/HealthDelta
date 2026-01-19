# HealthDelta — Operating Rules (HARD REQUIREMENTS)

This repository is run with strict, issue-driven Agile discipline and a Codex-auditable workflow.

## Non-negotiables

1) GitHub Issues are the system of record (hard stop)
- No code, refactors, formatting, renames, or behavior-changing docs without a GitHub issue that explains *why* first.
- If no issue exists: create one using the required template, then proceed.

2) Mandatory issue template
Every issue must use:

---
Story
As a <user/system>,
I want <capability>,
So that <clear outcome or value>.

Context / Why
Why this story matters now.
What risk, confusion, or limitation exists without it.

Acceptance Criteria
- Given <context>, when <action>, then <observable result>
- All criteria must be objective and testable.

Out of Scope
What this story explicitly does NOT attempt to solve.

Notes
Optional clarifications or constraints.
---

3) Trunk-based development
- `main` is always releasable.
- Short-lived branches; merge when acceptance criteria are met.
- No speculative/preparatory code.

4) TDD (required for non-trivial logic)
- Write failing tests first for non-trivial logic (especially identity resolution, parsing, anchors, dedupe).

5) Codex audit trail is mandatory
- Record substantial prompts in `.codex/prompts/`.
- Record each session in `.codex/sessions/YYYY-MM-DD/session_<n>.md`.
- Record architectural decisions as ADRs in `.codex/decisions/`.
- `.codex/` must never contain secrets.

6) TIME.csv is mandatory
- Every work session appends a row referencing a GitHub issue.

7) GitHub interaction
- Use `gh` CLI for issues/PRs. No direct REST API calls.

