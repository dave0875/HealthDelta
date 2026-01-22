# ISSUE-0022: Profile-to-pipeline UX recommendations

GitHub: https://github.com/dave0875/HealthDelta/issues/22

## Objective
Make `healthdelta export profile` more actionable by providing deterministic, share-safe “Next Steps” command recommendations based on what is present in an export.

## Context / Why
Profiling is most valuable when it guides the operator toward the correct command path (operator run vs pipeline run) without needing to re-read runbooks every time.

## Acceptance Criteria
- `profile.md` includes a deterministic “Next Steps” section with recommendations based on detected files.
- Recommendations are share-safe (no paths outside export root).
- Tests assert the section exists and is deterministic.

## Non-Goals
- Automatically executing any pipeline steps.

## Risks
- Risk: Recommendations drift from the CLI as flags evolve.
  - Mitigation: keep commands minimal and stable; tests assert key lines exist.

## Test Plan
- Local: `python3 -m unittest discover -s tests -p 'test_*.py'`
- CI: verify green run (Linux + macOS) with `ios-xcresult` artifact.

## Rollback Plan
- Revert Issue #22 commit(s) to remove the “Next Steps” section.

