# ISSUE-0066: CLI: progress indicators across pipeline (duckdb/reports/deid/bundle/operator)

GitHub: https://github.com/dave0875/HealthDelta/issues/66

## Objective
Extend progress indicators across all long-running HealthDelta CLI commands and add nested progress for the operator workflow.

## Context / Why
Issue #64 added the progress framework and integrated ingest + export. Remaining commands still perform long-running work without consistent progress output, especially `healthdelta run all` which chains multiple heavy phases.

## Acceptance Criteria
- DuckDB build/import emits progress (rows or files processed, throughput where feasible).
- Report generation and doctor note generation emit progress across key queries/writes.
- De-identification and share bundle creation emit progress across files processed/hashes computed.
- `healthdelta run all` emits nested progress: overall phases and sub-step progress.
- Progress output remains share-safe (no PHI/PII; no input paths).
- Tests validate progress output for at least one additional command and that nested progress is not confusing.

## Test Plan
- Local: `python3 -m unittest discover -s tests -p 'test_*.py' -v`
- CI: `CI` workflow green

