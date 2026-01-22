# ISSUE-0024: Operator identity persistence across runs

GitHub: https://github.com/dave0875/HealthDelta/issues/24

## Objective
Make `healthdelta run all` reuse a shared identity store so the same person gets a stable `canonical_person_id` across successive runs.

## Context / Why
Per-run identity causes person IDs to change across runs even when the same person appears in multiple exports, breaking longitudinal analysis and making collaboration harder.

## Acceptance Criteria
- Shared identity dir under `--state` (default: `<base_out>/state/identity`).
- NDJSON output remains deterministic and resolves `canonical_person_id` using the shared identity store.
- Synthetic integration test proves stable IDs across two runs with the same patient and no PII leakage.
- Update `docs/runbook_operator.md`.
- Audit artifacts: `.codex/prompts/issue_24.md`, session log, review, `TIME.csv`.
- CI green required before closing.

## Non-Goals
- Human confirmation workflow / UI.
- De-id rule changes.

## Risks
- Risk: NDJSON exporter cannot locate the shared identity store for operator runs.
  - Mitigation: explicitly detect `<base_out>/state/identity` during context resolution.

## Test Plan
- Local: `python3 -m unittest discover -s tests -p 'test_*.py'`
- CI: link green run + `ios-xcresult` artifact

## Rollback Plan
- Revert operator identity changes to restore per-run identity output.

