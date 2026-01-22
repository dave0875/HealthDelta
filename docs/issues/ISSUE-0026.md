# Issue 26 — DuckDB loader: append-safe ingestion using record_key (no duplicates)

GitHub: https://github.com/dave0875/HealthDelta/issues/26

## Objective
Make `healthdelta duckdb build` idempotent for the same NDJSON input by deduping on `record_key` (introduced in Issue #25).

## Context
Issue #25 adds a stable `record_key` to every NDJSON row. DuckDB ingestion must use it to prevent duplicate rows on repeated builds and to support incremental workflows.

## Acceptance Criteria (from GitHub issue)
- Extend `healthdelta duckdb build` behavior to support append-safe loading OR explicitly require `--replace` (choose one; document).
- If append-safe:
  - enforce a uniqueness constraint or deterministic dedupe on `record_key` per table
  - rerunning build against the same NDJSON input yields identical row counts and stable query results
- Update `docs/runbook_duckdb.md` with schema and dedupe rules.
- Synthetic tests prove:
  - building twice does not increase row counts
  - a few canonical queries remain stable across reruns
- CI green required before closing.

## Non-goals
- Cross-run compaction/merge.
- Dashboards or analytics.
- Schema migrations for old DB files (ok to require `--replace`).

## Risks
- DuckDB SQL compatibility across versions for conflict handling.
- Performance if dedupe is implemented with per-row existence checks (acceptable for this slice).

## Test Plan
- Unit/integration-style test invokes `healthdelta duckdb build` twice against the same synthetic NDJSON directory:
  - first run uses `--replace`
  - second run omits `--replace`
  - assert row counts remain unchanged and outputs contain no synthetic PII tokens.

## Rollback Plan
- Revert commits referencing Issue #26.
- Restore prior behavior (require `--replace`) if append-safe ingestion proves unreliable.

