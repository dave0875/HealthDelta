# ISSUE-0037: Python: ingest iOS NDJSON export directory into deterministic staging

GitHub: https://github.com/dave0875/HealthDelta/issues/37

## Objective
Enable deterministic ingestion of iOS-exported NDJSON artifacts into a staging directory for downstream DuckDB/reporting analysis.

## Context / Why
iOS incremental exports produce NDJSON (and a manifest). The Python toolchain needs a deterministic staging step so iOS exports can be verified and analyzed without Apple export.zip.

## Acceptance Criteria
- Given an iOS export directory containing NDJSON outputs, when running `healthdelta ingest ios`, then the tool validates inputs and writes a deterministic staging directory with a manifest.
- Given identical input bytes, when ingesting twice into different staging roots, then the staging `manifest.json` is byte-stable (no timestamps/absolute paths).

## Non-Goals
- HealthKit on-device collection.
- DuckDB loader changes (handled in Issue #38).

## Risks
- Risk: CLI change could break existing `healthdelta ingest` usage.
  - Mitigation: Keep `healthdelta ingest --input ...` behavior intact; add optional `ios` variant as a positional.

## Test Plan
- Local: `python3 -m unittest discover -s tests -p 'test_*.py'`
- CI: green run link + macOS `ios-xcresult` artifact

## Rollback Plan
- Revert the commit(s); iOS ingestion path removed without affecting existing export.zip ingestion.

