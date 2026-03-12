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

The app’s main screen is now the `Clinical Compass` dashboard. It keeps the primary care actions on the main screen and moves raw ORIN connection details into a secondary settings sheet.

Manual export flow:

1) Launch the app on the iPhone.
2) In the `Clinical Compass` dashboard, tap `Export`.
3) Approve Health access for the app if iOS prompts for it.
4) Wait for the export spinner to complete, then tap the top-right `Refresh` button if needed.

Expected result:
- the app writes a new run under `Documents/HealthDelta/<run_id>/`
- `manifest.json` appears beside `ndjson/observations.ndjson`
- the dashboard replaces `No sync data yet` with local sync details from the newest run

If export fails or Health access is denied, the dashboard shows an error in the `Needs attention` card.

## Direct upload to ORIN

The app supports direct upload for the newest completed run. The care-facing dashboard keeps upload actions visible, while the raw connection values live in `Connection settings`.

1) Produce a local run with `Export`.
2) Open `Connection settings` from the top-right slider icon.
3) Enter:
   - `Upload endpoint` (example: `http://192.168.1.223:8080`)
   - `Upload token` (must match `HEALTHDELTA_UPLOAD_TOKEN` on ORIN)
4) Dismiss the sheet.
5) On the main dashboard, tap `Sync to ORIN`.

Current behavior:
- The app zips the completed run directory locally.
- It creates an upload session with `POST /upload-sessions`.
- It uploads the archive in sequential chunks with `PUT /upload-sessions/{id}/chunks/{index}`.
- It finalizes the dataset with `POST /upload-sessions/{id}/finalize`.
- For iPhone export uploads, ORIN preserves each raw uploaded run archive under the active dataset directory and materializes a cumulative `export.zip` for analysis.
- Re-uploading the same iPhone run does not duplicate rows in the cumulative current dataset.
- On success, the app shows the returned dataset identifier and can fetch ORIN-generated insight cards with `GET /insights/current`.
- ORIN materializes deterministic analysis artifacts for the active dataset under:
  - `analysis/duckdb/run.duckdb`
  - `analysis/reports/summary.json`
  - `analysis/reports/summary.md`
  - `analysis/note/doctor_note.md`
- `GET /insights/current` derives its fallback cards from those ORIN-side artifacts, not directly from the raw uploaded NDJSON.
- By default, those insights are grounded in ORIN's cumulative current dataset, not only the newest incremental iPhone delta.
- When ORIN has a local Ollama runtime configured, it refines those artifact-grounded facts into more readable cards. If Ollama is unavailable or returns invalid output, the deterministic artifact-grounded cards are returned as-is.

Insight refresh behavior:
- The top-right `Refresh` action reloads local sync state and, when both ORIN endpoint and token are configured, also fetches the latest ORIN insight cards.
- The `Scope` card lets the operator choose:
  - `Evaluation window`: `All data`, `7 days`, `30 days`, or `90 days`
  - `Patient scope`: `All patients`, the known local iPhone record when available, or a manual `canonical_person_id` override
- Manual patient entry is intentionally secondary. Use it only when filtering to a different patient than the local iPhone export identity.
- Those controls affect both explicit dashboard refreshes and the automatic ORIN fetch that runs after a successful upload.
- On successful upload, the app immediately attempts an ORIN insights fetch.

Failure behavior:
- Missing/invalid endpoint or token surfaces an error in the dashboard.
- ORIN-side API failures are surfaced using the backend error detail when available.
- If the ORIN backend is only published on `127.0.0.1`, iPhone uploads will fail until ORIN is redeployed with `HEALTHDELTA_PUBLISHED_BIND_HOST=0.0.0.0`.
- The main dashboard intentionally does not show raw endpoint/token fields; those remain in `Connection settings` so the primary screen stays care-focused.

Headless validation hook:
- For operator validation from a tethered Mac, the app also honors these launch environment variables:
  - `HEALTHDELTA_AUTO_UPLOAD_ON_LAUNCH=1`
  - `HEALTHDELTA_AUTO_UPLOAD_BASE_URL=<http(s)://host:port>`
  - `HEALTHDELTA_AUTO_UPLOAD_TOKEN=<bearer token>`
- Equivalent launch arguments are also accepted:
  - `--healthdelta-auto-upload-on-launch`
  - `--healthdelta-auto-upload-base-url <http(s)://host:port>`
  - `--healthdelta-auto-upload-token <bearer token>`
- A file-based hook is also accepted at `Documents/HealthDelta/auto_upload.json` with JSON shape:
  - `{"base_url":"http://host:port","bearer_token":"..."}`
- When any one complete hook is present, the app refreshes the latest local run and attempts a one-shot upload on launch. This does not replace the normal dashboard-triggered flow.

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
