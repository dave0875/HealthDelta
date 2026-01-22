# ISSUE-0025: NDJSON schema version + record_key

GitHub: https://github.com/dave0875/HealthDelta/issues/25

## Objective
Add explicit schema versioning and a stable record key to canonical NDJSON rows so validation and downstream dedupe are deterministic.

## Context / Why
Downstream consumers (DuckDB, notebooks) need a stable per-record identifier and an explicit schema version to safely validate and deduplicate without re-parsing raw sources.

## Acceptance Criteria
- NDJSON exporter emits `schema_version` (int) and `record_key` (string) on every row.
- Validator enforces these fields and types.
- Docs updated to describe fields and derivation.
- Synthetic tests prove stability across reruns.
- Audit artifacts: `.codex/prompts/issue_25.md`, session log, review, `TIME.csv`.
- CI green required before closing.

## Non-Goals
- Full JSONSchema formalization.
- DuckDB loader changes (Issue #26).

## Risks
- Risk: Breaking downstream code that expects only `event_key`.
  - Mitigation: keep `event_key` for compatibility; introduce `record_key` as canonical.

## Test Plan
- Local: `python3 -m unittest discover -s tests -p 'test_*.py'`
- CI: link green run + `ios-xcresult` artifact

## Rollback Plan
- Revert the exporter/validator changes and restore prior NDJSON row shape.

