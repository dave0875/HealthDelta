# Issue #11 — Incremental runs + run registry (immutable prompt)

Issue: https://github.com/dave0875/HealthDelta/issues/11

Host constraint (authoritative execution rule)
- All repository mutations occur ONLY on Ubuntu host `GORF`.
- macOS runner is used ONLY via GitHub Actions for Xcode work; no repo mutation on macOS.

## Acceptance criteria (restated)

- Introduce a state directory (default `data/state/`) holding:
  - deterministic registry `runs.json`
  - stable pointer `LAST_RUN` (newline-terminated)
- Add CLI:
  - `healthdelta run register --run <run_dir> [--state <dir>] [--note <text>]`
  - `healthdelta pipeline run --input <export_dir> [--state <dir>] [--mode local|share] [--since last|<run_id>]`
- Incremental semantics for this slice:
  - no record-level diff
  - compute deterministic `input_fingerprint` (hash relpaths + sizes + sha256(bytes)); do not print raw PHI paths
  - run_id derived deterministically from `parent_run_id + input_fingerprint + pipeline_version_salt`
  - if fingerprint matches parent fingerprint: print “no changes detected”, exit 0, do not create new run or mutate outputs (except MAY write LAST_RUN if missing)
- Tests:
  - synthetic-only export directory trees
  - registry + LAST_RUN determinism and idempotency
  - same input twice yields no-op (per documented behavior)
  - no banned tokens / path leakage in registry or stdout/stderr
- Docs:
  - add `docs/runbook_incremental.md` and reference it from `AGENTS.md`
- Audit artifacts:
  - session log, review artifact, TIME.csv entry
- Close only after CI is green (Linux tests + macOS Xcode job artifacts).

## Key design choices (within scope)

- Registry format: `runs.json` as a single JSON object with a `runs` map keyed by `run_id` (stable ordering via `sort_keys=True`).
- Created-at: stored once at first registration; idempotent operations must not rewrite existing entries.
- Artifact pointers: stored as **relative paths** (e.g., `staging/<run_id>`) to avoid absolute host path leakage.
- No-op: if `--since` parent exists and fingerprints match, pipeline returns success early without running ingest/identity/deid.

## Plan

1) Add `healthdelta/state.py`
- Compute input fingerprints for directory (or file) inputs.
- Load/save `runs.json` deterministically.
- Read/write `LAST_RUN`.
- Helpers to register runs and update pointers.

2) Extend pipeline
- Update `healthdelta/pipeline.py` to accept `state_dir` and `since`.
- Compute parent run + parent fingerprint from registry.
- Compute new run_id deterministically and stage into `staging/<run_id>` (requires ingest override support).
- Register run and update LAST_RUN.

3) CLI wiring
- Add `healthdelta run register ...` subcommand.
- Add `--state` and `--since` flags to `healthdelta pipeline run`.

4) Tests + docs
- Add `tests/test_incremental.py` with synthetic directories and subprocess CLI invocations.
- Add `docs/runbook_incremental.md` and reference from `AGENTS.md`.

5) Closeout
- Run tests locally, push, verify CI green.
- Write session log + review + TIME.csv entry.
- Comment/close Issue #11 with CI evidence.

