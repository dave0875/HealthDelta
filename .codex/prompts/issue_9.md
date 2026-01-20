# Issue #9 — DuckDB loader from canonical NDJSON exports (immutable prompt)

Issue: https://github.com/dave0875/HealthDelta/issues/9

Host constraint (authoritative execution rule)
- All repository mutations occur ONLY on Ubuntu host `GORF`.
- macOS runner is used ONLY via GitHub Actions for Xcode work; no repo mutation on macOS.

## Acceptance criteria (restated)

- Add headless CLI commands:
  - `healthdelta duckdb build --input <ndjson_dir> --db <path> [--replace]`
  - `healthdelta duckdb query --db <path> --sql <sql> [--out <path>]`
- Build creates deterministic DuckDB tables for canonical NDJSON streams (Issue #8):
  - `observations`, `documents`, optional `medications`, optional `conditions`
- Every table includes: `canonical_person_id`, `source`, `source_file`, `event_time`, `run_id` plus stream-specific columns.
- Ingestion must be streaming-safe (no Python full-file loads).
- Loader behavior must either be append-safe or require `--replace`; choose and document.
- Tests are synthetic-only and verify schema, row counts, deterministic query outputs, and absence of PII.
- Document schema + usage in `docs/runbook_duckdb.md` and reference it from `AGENTS.md`.
- Produce audit artifacts (session log, review, TIME.csv row) and close only after CI is green with artifacts.

## Scope decisions (within acceptance criteria)

- Loader behavior: **explicitly requires `--replace`** to overwrite an existing database; otherwise it errors if `--db` already exists.
  - Rationale: keeps behavior simple and deterministic for MVP; append-safe dedupe is deferred.
- Determinism goal:
  - Stable query results are enforced by deterministic schema + deterministic ingestion order + explicit guidance to use `ORDER BY` in queries.
  - Byte-stable DB files are targeted “where feasible”; DuckDB file bytes may vary across DuckDB versions/platforms, but results should be stable.

## Plan

1) Dependency
- Add Python dependency `duckdb` in `pyproject.toml`.

2) Implementation (`healthdelta/duckdb_tools.py`)
- `build_duckdb(input_dir, db_path, replace)`
  - Validate input NDJSON filenames (`observations.ndjson`, `documents.ndjson`, optional others).
  - Create tables with explicit types.
  - Load using DuckDB JSON reader (newline-delimited) to avoid Python reading full files.
  - Insert rows in a stable way and optionally create indexes for common query patterns.
- `query_duckdb(db_path, sql, out_path)`
  - Execute SQL.
  - Emit deterministic output (default: print to stdout as CSV with header; if `--out`, write the same).
  - Document that deterministic output requires deterministic SQL (use `ORDER BY`).

3) CLI wiring (`healthdelta/cli.py`)
- Add `duckdb build` and `duckdb query` subcommands.

4) Tests (`tests/test_duckdb.py`)
- Synthetic NDJSON fixtures written during test setup (no real health data).
- Assert:
  - DB file created
  - expected tables exist
  - row counts match
  - a few deterministic queries return expected results
  - schema and query outputs contain no synthetic PII strings (names/DOB/raw ids)

5) Docs
- Add `docs/runbook_duckdb.md` describing schema, loader behavior (`--replace`), and deterministic query guidance.
- Update `AGENTS.md` to reference runbook.

6) Closeout
- Run tests locally; push; verify CI green (Linux + macOS) with artifacts.
- Write session log and AI-on-AI review, update TIME.csv.
- Comment on Issue #9 with CI run evidence; close.

## Privacy rules

- Loader must not introduce PII; it operates on canonical NDJSON that is already share-safe.
- Tests use synthetic strings only and assert those strings never appear in DuckDB schema or query outputs.

