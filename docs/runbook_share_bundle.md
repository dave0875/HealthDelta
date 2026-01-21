# Runbook: Share bundle (`healthdelta share bundle`)

Purpose: package share-safe artifacts into a single deterministic archive for collaboration, without including staging/PII.

## Command

`healthdelta share bundle --run <base_out>/<run_id> --out <path>.tar.gz`

## What is included

Only these subtrees under `<base_out>/<run_id>/` (when present):
- `deid/`
- `ndjson/`
- `duckdb/`
- `reports/`
- `note/`

Plus a share-safe run registry snippet:
- `<run_id>/registry/run_entry.json` (derived from `<base_out>/state/runs.json` when present)

## What is excluded

- `staging/` and any raw inputs
- `identity/` (may contain names)
- any network upload/exfiltration (this command is filesystem-only)

## Determinism

The archive is built to be byte-stable for unchanged inputs (as feasible):
- stable archive member ordering (sorted by path)
- normalized tar metadata (mtime/uid/gid)
- normalized gzip header timestamp

