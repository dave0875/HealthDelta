---
Story
As a maintainer,
I want CI to enforce that every change has evidence artifacts and updated audit logs,
So that governance and correctness are programmatically guaranteed.

Context / Why
Guardrails must be as strict as the policy demands.

Acceptance Criteria
- CI fails if `.ai/time/time.csv` or `.ai/sessions/` is not updated for code changes.
- CI uploads evidence artifacts (test logs, validation reports).
- Tests/CI steps are documented and deterministic.

Out of Scope
- Historical backfill beyond current changes.
---
