# Issue #12 — Operator command: one-shot run (immutable prompt)

Issue: https://github.com/dave0875/HealthDelta/issues/12

Host constraint (authoritative execution rule)
- All repository mutations occur ONLY on Ubuntu host `GORF`.
- macOS runner is used ONLY via GitHub Actions for Xcode work; no repo mutation on macOS.

## Acceptance criteria (restated)

- Add a single high-level orchestration command:
  - `healthdelta run all --input <export_dir> [--state <dir>] [--since last|<run_id>] [--mode local|share] [--out <base_out>]`
- Default `--mode share`.
- Uses Issue #11 incremental behavior:
  - deterministic `input_fingerprint`
  - deterministic `run_id`
  - no-op on unchanged input (no new run, no output mutation) with deterministic console summary
- For a new run, perform in order:
  1) pipeline run (ingest → identity → deid)
  2) NDJSON export (Issue #8)
  3) DuckDB build (Issue #9)
  4) Reports build (Issue #10)
- Output layout under `<base_out>/<run_id>/`:
  - `staging/`, `identity/`, `deid/`, `ndjson/`, `duckdb/run.duckdb`, `reports/`
- Update run registry (Issue #11) to include produced artifact pointers.
- Tests are synthetic-only and prove end-to-end determinism, no-op behavior, and no banned tokens in outputs.
- Docs: add `docs/runbook_operator.md` and reference from `AGENTS.md`.
- Audit: session log, review artifact, TIME.csv entry.
- Close only after CI is green (Linux tests + macOS Xcode job artifacts).

## Design decisions (within scope)

- New command name: `healthdelta run all` (Option A).
- Output base default: `data` (produces `data/<run_id>/...` plus `data/state/...` by default).
- Registry updates:
  - initial registration writes `runs.json` + `LAST_RUN`
  - post-stages update the run entry’s `artifacts.*` pointers deterministically
- Share mode guarantees:
  - NDJSON is generated from `deid/` inputs
  - DuckDB and reports are built solely from canonical NDJSON (no staging content parsed directly)
  - operator outputs are share-safe; staging is not share-safe by definition.

## Plan

1) Add `healthdelta/operator.py`
- Implement `run_all(...)` that:
  - resolves `state_dir` (default `<base_out>/state`)
  - computes incremental decision using Issue #11 fingerprint and registry
  - on no-op: prints deterministic artifact summary and exits 0 without touching files
  - on new run: creates `<base_out>/<run_id>/...` directories and orchestrates stages

2) Update state helpers
- Add an `update_run_artifacts(...)` helper to update pointers deterministically without rewriting existing entries.
- Expand artifact pointers to include identity/ndjson/duckdb/reports paths as needed.

3) CLI wiring
- Add `healthdelta run all` subcommand in `healthdelta/cli.py`.

4) Tests + docs
- Add `tests/test_operator.py` to run end-to-end (synthetic export dir; share mode default):
  - first run produces outputs
  - second run no-op and no file bytes change
  - outputs contain no banned tokens
  - report `summary.json`/`summary.md` are byte-stable across reruns
- Add `docs/runbook_operator.md` and reference from `AGENTS.md`.

5) Closeout
- Run tests, push, verify CI green.
- Write `.codex/sessions/YYYY-MM-DD/session_10.md`, `docs/reviews/YYYY-MM-DD_12.md`, update `TIME.csv`.
- Comment Issue #12 with CI evidence and close.

