# ISSUE-0019: Pipeline/operator remove redundant CDA staging

GitHub: https://github.com/dave0875/HealthDelta/issues/19

## Objective
Ensure there is exactly one authoritative implementation for staging `export_cda.xml` (ingest), reducing divergence risk across pipeline/operator flows.

## Context / Why
As staging support for `export_cda.xml` expands, duplicating staging logic in multiple orchestration layers increases the risk of inconsistent layouts and subtle bugs. Consolidating keeps run layouts predictable and makes downstream deid/export behavior easier to reason about.

## Acceptance Criteria
- Pipeline and operator no longer implement separate CDA staging when ingest already stages `export_cda.xml`.
- Share mode deid still includes `export_cda.xml` when present in the input export.
- Tests prove CDA presence through the full pipeline/operator path.

## Non-Goals
- Changes to CDA de-identification rules.
- Broader refactors of ingest layout or clinical JSON staging (handled in Issue #18).

## Risks
- Risk: older staged runs may be missing `export_cda.xml` in layout/staging.
  - Mitigation: keep CDA handling optional downstream; only remove *redundant* staging in pipeline/operator.

## Test Plan
- Local: `python3 -m unittest discover -s tests -p 'test_*.py'`
- CI: verify green run (Linux + macOS) with `ios-xcresult` artifact.

## Rollback Plan
- Revert Issue #19 commit(s) to restore prior redundant staging behavior (not preferred, but safe).

