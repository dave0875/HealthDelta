# Pipeline Runbook (Orchestrator)

## Goal
Run the HealthDelta bootstrap pipeline as a single command that produces deterministic, auditable artifacts (staging, identity, and optionally de-identified share outputs) plus a non-PII run report.

## Command

- `healthdelta pipeline run --input <path> [--out <base_dir>] [--mode local|share] [--run-id <run_id>] [--skip-deid]`

## Common invocations

Local mode (default; no de-id):
- `healthdelta pipeline run --input /path/to/export_dir --out data --mode local`

Share mode (runs de-id):
- `healthdelta pipeline run --input /path/to/export_dir --out data --mode share`

Expected run-id (guardrail):
- `healthdelta pipeline run --input /path/to/export_dir --out data --mode share --run-id <expected>`

Skip de-id even in share mode (debugging only):
- `healthdelta pipeline run --input /path/to/export_dir --out data --mode share --skip-deid`

## Outputs
Under `<base_dir>`:
- `staging/<run_id>/` (from ingest)
  - `manifest.json`, `layout.json`, plus staged copies under `source/`
  - `run_report.json` (pipeline report; no PII)
- `identity/` (from identity build)
  - `people.json`, `aliases.json`
- `deid/<run_id>/` (share mode only, unless skipped)
  - `mapping.json`, `manifest.json`, `layout.json`, and de-identified copies

## Rerun behavior
- Re-running the same input is safe:
  - ingest uses deterministic `run_id`
  - identity uses stable `alias_key` to avoid duplicating identical alias observations
  - share mode de-id overwrites output files under `deid/<run_id>/`

## Privacy
- The pipeline does not upload data; it operates on local filesystem only.
- `run_report.json` must not include PII (no names, DOB, MRNs).

