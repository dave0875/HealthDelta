# ISSUE-0016: Living plan/backlog + local issue artifact template

GitHub: https://github.com/dave0875/HealthDelta/issues/16

## Objective
Create an in-repo, share-safe living plan/backlog and a lightweight local issue artifact template to keep autonomous issue-driven development prioritized and auditable.

## Context / Why
HealthDelta is operating under strict issue-driven governance with Codex audit artifacts. A small in-repo plan/backlog reduces drift and makes continuity easier as the backlog grows.

## Acceptance Criteria
- Add a living plan/backlog document that summarizes current capabilities and lists the next 5–10 logical issues in priority order.
- Add this local issue artifact (this file) and a reusable template under `docs/issues/`.
- The plan/backlog references GitHub issues by URL.
- No secrets and no PII in the new documents.
- Tests pass; CI is green; Issue #16 is closed with evidence.

## Non-Goals
- No pipeline behavior changes.
- No refactors or renames.

## Risks
- Risk: plan/backlog becomes stale.
  - Mitigation: keep it short and update it once per issue (or when priorities change).

## Test Plan
- Local: `python3 -m unittest discover -s tests`
- CI: confirm green run (Linux + macOS) with `ios-xcresult` artifact.

## Rollback Plan
- Revert the documentation commits and remove `docs/issues/` and plan file.

