# ISSUE-0038: DuckDB: load iOS NDJSON exports (subset mapping)

GitHub: https://github.com/dave0875/HealthDelta/issues/38

## Objective
Allow the DuckDB loader to ingest iOS-exported NDJSON artifacts via a documented subset mapping so iOS incremental exports can be queried with existing tools.

## Context / Why
The current loader expects canonical export pipeline NDJSON files and requires streams iOS does not yet emit. We need a safe subset mapping rather than full schema parity.

## Acceptance Criteria
- Given an iOS export directory containing `manifest.json` and `ndjson/observations.ndjson`, when running `healthdelta duckdb build`, then the DB builds successfully and rows are queryable.
- Given rerunning `duckdb build` on the same iOS input without `--replace`, then no duplicates are inserted (append-safe).
- Mapping is documented in `docs/runbook_duckdb.md`.

## Non-Goals
- Full schema parity between iOS and export.zip pipelines.

## Risks
- Risk: Relaxing file requirements could hide mistakes for canonical inputs.
  - Mitigation: Only relax requirements when the iOS input layout is detected (manifest.json + ndjson/ directory).

## Test Plan
- Local: `python3 -m unittest discover -s tests -p 'test_*.py'`
- CI: green run link + macOS `ios-xcresult` artifact

## Rollback Plan
- Revert commit(s); iOS inputs revert to unsupported and canonical pipeline behavior remains unchanged.

