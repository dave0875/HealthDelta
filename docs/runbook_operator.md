# Runbook: Operator Command (`healthdelta run all`)

This runbook describes the preferred one-command “operator path” for HealthDelta: ingest + identity + de-id (optional) + NDJSON + DuckDB + reports + Doctor’s Note.

## Command

```bash
healthdelta run all --input <export_dir_or_export.zip> [--out <base_out>] [--state <state_dir>] [--since last|<run_id>] [--mode local|share]
```

Defaults:
- `--out data`
- `--state <base_out>/state`
- `--since last`
- `--mode share`

Notes:
- Runs are local-only: no network access, no uploads.
- `share` mode is the default and is the recommended operator workflow.
- Doctor’s Note is generated automatically by default; use `--skip-note` to disable.

## Output layout

For a created run, outputs are written under:

```
<base_out>/<run_id>/
  staging/
  deid/              (share mode)
  ndjson/
  duckdb/run.duckdb
  reports/
  note/
<base_out>/state/
  runs.json
  LAST_RUN
  identity/          (local-only canonical identity store; not share-safe)
```

## Share-safe defaults

In `--mode share`:
- NDJSON is exported from `<base_out>/<run_id>/deid` (not raw staging).
- DuckDB is built only from canonical NDJSON outputs.
- Reports are built only from DuckDB and contain no names/DOB/free-text patient identifiers.
- Doctor’s Note is generated from DuckDB and is share-safe by design; see `docs/runbook_note.md`.

Reminder: `<base_out>/<run_id>/staging` is not share-safe by definition and must not be shared.

Identity note:
- Canonical identity is stored under `<base_out>/state/identity` so `canonical_person_id` can remain stable across runs.
- This directory is local-only and must not be shared (it may contain names); share bundles exclude it by design.

## Incremental / no-op behavior

`healthdelta run all` uses Issue #11’s incremental semantics:
- Computes a deterministic, share-safe input fingerprint.
- Uses `<base_out>/state/LAST_RUN` as the parent by default.
- If the fingerprint matches the parent run’s fingerprint:
  - exits successfully with `status=no_changes`
  - prints a deterministic summary of the current run and artifact locations
  - does not create a new run directory and does not mutate outputs

## Examples

First run (share-safe defaults):

```bash
healthdelta run all --input /path/to/apple_health_export_dir --out data
```

Rerun with unchanged input (no-op):

```bash
healthdelta run all --input /path/to/apple_health_export_dir --out data
```

Force local mode (not share-safe):

```bash
healthdelta run all --input /path/to/apple_health_export_dir --out data --mode local
```
