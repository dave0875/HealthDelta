# Runbook: CLI progress indicators

HealthDelta CLI commands that may process large datasets emit share-safe progress indicators.

## Progress output rules (share-safe)
- Progress output must never include PHI/PII.
- Allowed: counts, sizes, durations, step names, versions, run ids (hashes), and generic filenames like `export.xml`.
- Avoid printing input paths (they may contain patient names in directory names).

## Flags
- `--progress {auto,always,never}` (default `auto`)
  - `auto`: interactive updates when stderr is a TTY; otherwise line-based progress logs
  - `always`: force progress output even when non-TTY (line-based)
  - `never`: suppress progress output (still prints a final per-phase summary)
- `--log-progress-every N` (default `5`) seconds
  - Applies to line-based progress output to avoid high overhead.
- `--quiet`
  - Reduces progress verbosity (keeps phase markers and summary).

## Examples
- Export NDJSON with progress:
  - `healthdelta --progress auto export ndjson --input data/staging/<run_id> --out data/ndjson --mode local`
- Force line-based progress (useful for logs):
  - `healthdelta --progress always --log-progress-every 2 export ndjson --input ... --out ...`
- Disable progress (keep summary only):
  - `healthdelta --progress never ingest --input export.zip --out data/staging`

