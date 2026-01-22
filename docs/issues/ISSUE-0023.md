# ISSUE-0023: Plan refresh (extend backlog beyond #22)

GitHub: https://github.com/dave0875/HealthDelta/issues/23

## Objective
Keep the living plan/backlog current and explicit so autonomous issue-driven development remains disciplined and auditable.

## Context / Why
Issues #17–#22 are complete. The living plan must be updated to avoid drift and to clearly enumerate the next 10 issues.

## Acceptance Criteria
- Update `docs/plan.md` to:
  - mark Issues #17–#22 as completed
  - add Issues #23–#32 (links + one-line intent)
  - remain share-safe
- Add immutable prompt: `.codex/prompts/issue_23.md`
- Add session log + review artifact + `TIME.csv` row
- CI green (Linux + macOS with `ios-xcresult`) before closing

## Non-Goals
- Implementing any of Issues #24–#32.

## Risks
- Risk: plan becomes stale and autonomous work drifts.
  - Mitigation: update plan at each “backlog boundary” and keep links current.

## Test Plan
- Local: `python3 -m unittest discover -s tests -p 'test_*.py'` (sanity)
- CI: link green run + `ios-xcresult` artifact

## Rollback Plan
- Revert the plan changes and re-apply with corrected issue links.

