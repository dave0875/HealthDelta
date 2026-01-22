# ISSUE-0041: CI: publish Linux unit test artifacts (and JUnit if feasible)

GitHub: https://github.com/dave0875/HealthDelta/issues/41

## Objective
Publish Linux unit test output as a CI artifact to improve auditability and debugging.

## Context / Why
macOS CI already uploads `ios-xcresult`. Persisting Linux test logs provides standardized evidence and speeds up triage when failures occur.

## Acceptance Criteria
- Given a CI run on Linux, when unit tests run, then the full unittest output is uploaded as an artifact with a deterministic name.
- If feasible without introducing a new test framework/dependency, also publish JUnit; otherwise document why it is skipped.
- CI is green before closing.

## Non-Goals
- Switching from `unittest` to `pytest` or adding JUnit-only dependencies.

## Risks
- Risk: Artifacts include sensitive output if tests print fixture contents.
  - Mitigation: Keep fixtures synthetic and keep tests from printing input payloads.

## Test Plan
- Local: `python3 -m unittest discover -s tests -p 'test_*.py' -v`
- CI: green run link + verify `linux-unittest` artifact exists.

## Rollback Plan
- Revert `.github/workflows/ci.yml` changes; no runtime code impacted.
