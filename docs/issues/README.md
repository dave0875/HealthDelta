# Local Issue Artifacts

GitHub Issues are the system of record for *why* work is done.

This directory provides a lightweight, share-safe local artifact for each issue to make execution auditable and repeatable across sessions (especially for autonomous work).

## Naming

- Use `ISSUE-XXXX.md` where `XXXX` is the GitHub issue number padded to 4 digits.
- Example: Issue #16 → `ISSUE-0016.md`.

## Template (copy for each issue)

```markdown
# ISSUE-XXXX: <title>

GitHub: <issue URL>

## Objective
One sentence describing user value.

## Context / Why
Why this matters now.

## Acceptance Criteria
- Given …

## Non-Goals
Explicitly out of scope.

## Risks
- Risk: …
  - Mitigation: …

## Test Plan
- Local: `python3 -m unittest discover -s tests`
- CI: link to green run + artifacts

## Rollback Plan
- How to revert safely if needed.
```

## Privacy

Local issue artifacts must remain share-safe:
- no secrets, tokens, or credentials
- no PII/PHI
- no absolute local paths that may contain names

