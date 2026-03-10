# Runbook: iOS Incremental Exports (Artifacts + Ingestion)

This runbook describes the iOS incremental export artifacts produced by the HealthDelta iOS app and how to ingest them into the Python toolchain on your workstation.

## Privacy / Safety

- Treat all iOS export directories as sensitive health data.
- Do not commit exports, staging directories, or databases to Git.
- Do not upload iOS export directories to GitHub Actions artifacts.
- Use share-safe workflows only (`healthdelta deid`, `healthdelta share bundle`, `healthdelta share verify`) when you need to collaborate.

## Where iOS writes outputs

The iOS app writes outputs under the app sandbox Documents directory using a deterministic layout:

- `Documents/HealthDelta/<run_id>/ndjson/observations.ndjson`
- `Documents/HealthDelta/<run_id>/manifest.json`

`<run_id>` is determined by the iOS exporter/orchestrator. In tests and examples it may be a simple string; in production it should be treated as an opaque identifier.

## What files exist

Minimum artifacts (current iOS skeleton):

- `ndjson/observations.ndjson`
  - one JSON object per line
  - includes `canonical_person_id`, stable HealthKit `source_id`, and `record_key`
  - `record_key` is derived from the stable HealthKit sample identity rather than only visible time/value fields
- `manifest.json`
  - deterministic summary of run outputs (run_id, hashes/sizes, row counts)

Anchor persistence artifacts:
- Anchors are persisted separately by the iOS app (file-backed anchor store). These files are required for incremental continuation on-device, but are not required for Python ingestion.

## Current manual export flow

The app’s first user-facing export path is a manual dashboard action:

1) Launch the app on the iPhone.
2) Tap `Export Now` in the `Sync Status` section.
3) Approve Health access for the app if iOS prompts for it.
4) Wait for the export to complete, then tap `Refresh` if needed.

Expected result:
- the app writes a new run under `Documents/HealthDelta/<run_id>/`
- `manifest.json` appears beside `ndjson/observations.ndjson`
- the dashboard replaces `No sync data yet` with local sync details from the newest run

If export fails or Health access is denied, the dashboard shows an error in the `Needs attention` section.

## Transfer to workstation (operator workflow)

Goal: copy a single run directory (`<run_id>/`) from the device to your workstation without modifying it.

Recommended approach:
1) Copy the run directory out of the app sandbox using your preferred device transfer mechanism.
2) Store it locally under a non-repo directory (example: `~/HealthDelta/ios_exports/<run_id>/`).
3) Keep the directory private; do not publish it.

### Mac to ORIN handoff (validated operator path)

Once the iPhone run has been copied to the Mac, you can transfer the same run directory to ORIN for local ingest/reporting there:

```bash
rsync -az ~/HealthDelta/ios_exports/<run_id>/ dbarker@orin.local:~/ios_exports/<run_id>/
```

Then on ORIN:

```bash
PYTHONPATH=$HOME/HealthDelta-temp python3 -m healthdelta ingest ios \
  --input ~/ios_exports/<run_id> \
  --out ~/ios_stage_out

PYTHONPATH=$HOME/HealthDelta-temp python3 -m healthdelta duckdb build \
  --input ~/ios_exports/<run_id> \
  --db ~/ios_duckdb_out/run.duckdb \
  --replace

PYTHONPATH=$HOME/HealthDelta-temp python3 -m healthdelta report build \
  --db ~/ios_duckdb_out/run.duckdb \
  --out ~/ios_report_out \
  --mode share
```

This is the currently validated path for `iPhone -> Mac -> ORIN`.

## Ingest into Python toolchain

### Option A (recommended): stage first, then analyze

Stage the iOS export into a deterministic staging directory:

```bash
healthdelta ingest ios --input <ios_run_dir> --out data/staging
```

This produces a new deterministic staging run directory under `data/staging/<staging_run_id>/` that contains:
- `ndjson/observations.ndjson`
- `source/ios/manifest.json` (copied input manifest)
- `manifest.json` (staging manifest; deterministic; share-safe metadata only)

Then build DuckDB and reports:

```bash
healthdelta duckdb build --input data/staging/<staging_run_id> --db data/duckdb/run.duckdb --replace
healthdelta report build --db data/duckdb/run.duckdb --out data/reports --mode share
```

### Option B: build DuckDB directly from iOS export dir

If you do not need staging, `duckdb build` can also load directly from an iOS run directory that contains `manifest.json` and `ndjson/observations.ndjson`:

```bash
healthdelta duckdb build --input <ios_run_dir> --db data/duckdb/run.duckdb --replace
```

Notes:
- Direct iOS-run DuckDB build is the currently validated ORIN path for copied iPhone exports.
- Duplicate iOS observation rows with the same `record_key` are deduplicated deterministically during a fresh DuckDB build.

## Share-safe collaboration

If you need to share results, do not share the iOS export directory.
Instead, share only:
- de-identified pipeline outputs, and/or
- reports and share bundles produced from share-safe inputs.
