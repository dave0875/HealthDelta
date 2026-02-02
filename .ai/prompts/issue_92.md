---
Story
As a maintainer,
I want CI guardrails that enforce governance and issue discipline automatically,
So that “one issue per PR” and required audit artifacts are programmatically guaranteed.

Context / Why
Recent work was done across multiple issues before PRs/CI; this must be prevented by guardrails rather than manual discipline.

Acceptance Criteria
- Given a PR, when CI runs, then it fails if commit messages contain more than one distinct `Issue: #NN` value (enforce one issue per PR).
- Given a PR, when CI runs, then it fails if the PR title/body does not include the same `Issue: #NN`.
- Given code or docs changes (excluding `.ai/`), when CI runs, then it fails if `.ai/prompts/issue_N.md`, a session entry for today, and a `.ai/time/time.csv` line for that Issue are missing.
- Given changes to `.ai/prompts/issue_N.md`, when CI runs, then it fails unless the file is new (immutability enforcement).
- CI uploads required evidence artifacts for tests/validation (logs + results) with deterministic names.

Out of Scope
- Changing acceptance criteria for existing issues.
- Non-CI enforcement (local hooks) unless explicitly added in a follow-up issue.

Notes
- Prefer repository-local scripts; avoid network calls in CI.
---
