# Session 9 — 2026-01-21

Issues worked
- #11 Incremental pipeline: run registry + "since last run" support (deterministic, share-safe)

Execution environment
- Repository mutations executed on Ubuntu host: `GORF`

Work summary
- Created Issue #11 and recorded immutable prompt: `.codex/prompts/issue_11.md`.
- Added a durable state directory concept (default `<base_out>/state`, with repo default `data/state`):
  - `runs.json` deterministic registry keyed by `run_id`
  - `LAST_RUN` stable pointer to latest run id
- Implemented incremental pipeline semantics (lineage + fingerprint, not record diffs):
  - deterministic `input_fingerprint` (sha256 over relpath+size+sha256(bytes))
  - deterministic `run_id = sha256(pipeline_salt + parent_run_id + input_fingerprint)`
  - no-op behavior when fingerprint matches parent (“no changes detected”)
- Added run registry command:
  - `healthdelta run register --run <run_dir> [--state <dir>] [--note <text>]`
- Added synthetic-only tests covering:
  - registry determinism/idempotency
  - LAST_RUN updates
  - no-op behavior for identical inputs
  - no leakage of banned tokens / input path names
- Added documentation runbook: `docs/runbook_incremental.md` and referenced it from `AGENTS.md`.

Local verification
- `python3 -m unittest discover -s tests -p 'test_*.py'` (pass; DuckDB-dependent tests skip without duckdb installed locally)

Review
- Wrote AI-on-AI review notes: `docs/reviews/2026-01-21_11.md`

CI evidence
- CI run (green): TBD (populate after push + CI completion)

