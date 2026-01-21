# Runbook: Incremental Runs + Run Registry (`data/state/`)

Issue #11 introduces a durable, local run registry that enables “since last run” incremental operation.

## What “incremental” means (in this issue)

This issue does **not** attempt record-level diffs inside HealthKit `export.xml`.

Instead, an incremental run means:
- each new input export produces a new run (new `run_id`)
- the new run stages the full input export (same staging behavior as Issue #4)
- the run registry records lineage (`parent_run_id`) and an `input_fingerprint` so duplicates can be detected deterministically

If the input fingerprint matches the parent fingerprint, the pipeline exits successfully with:
- `no changes detected`
- no new run directories are created

## State directory layout

Default state directory: `data/state/` (or `<base_out>/state` when using `--out <base_out>`).

Files:
- `runs.json`: deterministic registry (stable JSON formatting and ordering)
- `LAST_RUN`: latest run id pointer (newline-terminated)

## Fingerprints and run_id derivation

### input_fingerprint

`input_fingerprint` is deterministic and share-safe:
- computed as sha256 over all files under the input directory:
  - relative path (within the input dir)
  - file size
  - sha256(file bytes)
- the registry does not store the absolute input path

### run_id

`run_id` is derived deterministically from:
- `parent_run_id` (empty for the first run)
- `input_fingerprint.sha256`
- a constant pipeline version salt (`healthdelta_pipeline_v1`)

## Commands

### Pipeline run (stateful)

```bash
healthdelta pipeline run --input <export_dir> --out <base_out> [--state <dir>] [--mode local|share] [--since last|<run_id>]
```

Behavior:
- default parent selector is `--since last`
- registry is updated with the new run entry and `LAST_RUN` is updated
- if the input fingerprint matches the parent fingerprint, exits successfully with `no changes detected`

### Register an existing run

```bash
healthdelta run register --run <run_dir> [--state <dir>] [--note <text>]
```

Registers a pre-existing run directory (typically a staging run directory) and updates `LAST_RUN` deterministically.

## Recommended workflow

1) Initial run:
```bash
healthdelta pipeline run --input <export_dir> --out data --mode local
```

2) Repeat as new exports arrive:
```bash
healthdelta pipeline run --input <export_dir> --out data --mode local --since last
```

3) From a run, generate downstream artifacts (separate steps/issues):
- NDJSON: `healthdelta export ndjson ...`
- DuckDB: `healthdelta duckdb build ...`
- Reports: `healthdelta report build ...`

