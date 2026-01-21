# Issue #10 — Deterministic share-safe summary reports from DuckDB (immutable prompt)

Issue: https://github.com/dave0875/HealthDelta/issues/10

Host constraint (authoritative execution rule)
- All repository mutations occur ONLY on Ubuntu host `GORF`.
- macOS runner is used ONLY via GitHub Actions for Xcode work; no repo mutation on macOS.

## Acceptance criteria (restated)

- Add `healthdelta report build --db <path> --out <dir> [--mode local|share]`.
- (Optional but encouraged) Add `healthdelta report show --db <path>` that prints a deterministic summary and writes no files.
- `report build` writes deterministic, share-safe artifacts:
  - `summary.json`, `summary.md`
  - `coverage_by_person.csv`
  - `coverage_by_source.csv`
  - `timeline_daily_counts.csv` (when `event_time` is available)
- Report contents come from DuckDB tables (`observations`, `documents`, optional `medications`, optional `conditions`):
  - per-table: total rows, min/max event_time, distinct canonical_person_id, counts by source
  - per-person: rows per table, min/max event_time across all tables, top-N record types (if supported)
- Privacy: never emit names/DOB/free-text identifiers; use `canonical_person_id` only.
- Determinism: outputs are byte-stable for the same DB (stable ordering, formatting, ISO 8601 timestamps).
- Tests: synthetic-only; generate DB via NDJSON→duckdb build pathway; verify files, metrics, no banned tokens, and byte-stability for summary.json/md.
- Docs: add `docs/runbook_reports.md` and reference from `AGENTS.md`.
- Audit artifacts: session log, review artifact, TIME.csv entry.
- Close only after CI is green (Linux tests + macOS Xcode job with ios-xcresult artifact).

## Implementation decisions (within scope)

- Reports are always share-safe; `--mode` is accepted for future strictness but does not change output content in MVP.
- No non-deterministic “generated_at” timestamps are included in outputs (to preserve byte stability).
- Timeline output uses `event_time` date buckets when `event_time` is not NULL.

## Plan

1) Tests first
- Add `tests/test_reports.py`:
  - generate tiny synthetic NDJSON dir
  - build DB via `healthdelta duckdb build --replace`
  - run `healthdelta report build` twice
  - assert artifacts exist, metrics match expected, banned tokens absent, and summary.json/md bytes identical

2) Implementation
- Add `healthdelta/reporting.py`:
  - connect to DuckDB read-only
  - detect which tables exist
  - run canned aggregate queries with explicit ordering
  - write:
    - JSON with stable serialization (sorted keys, stable separators, newline)
    - Markdown derived from JSON with stable ordering
    - CSVs with stable headers and stable row ordering
- Wire CLI in `healthdelta/cli.py`:
  - `report build` and `report show`

3) Docs
- Add `docs/runbook_reports.md` documenting:
  - how to run
  - output files and meaning
  - privacy guarantees and limitations
- Update `AGENTS.md` to reference runbook.

4) Closeout
- Run tests locally; push; verify CI green (Linux + macOS) with artifacts.
- Write session log `.codex/sessions/YYYY-MM-DD/session_8.md`, AI review `docs/reviews/YYYY-MM-DD_10.md`, and update `TIME.csv`.
- Comment Issue #10 with CI run link and close.

