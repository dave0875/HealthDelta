# Runbook: DuckDB Loader + Query (`healthdelta duckdb`)

This runbook describes how to build and query a local DuckDB database from HealthDelta canonical NDJSON exports (Issue #8).

## Commands

Build:

```bash
healthdelta duckdb build --input <ndjson_dir> --db <path> [--replace]
```

Query:

```bash
healthdelta duckdb query --db <path> --sql <sql> [--out <path>]
```

Notes:
- No network access: commands operate on local filesystem only.
- Deterministic results require deterministic SQL (use `ORDER BY`).

## Loader behavior

- If `--db` does not exist, the loader creates it and loads the NDJSON streams.
- If `--db` exists:
  - with `--replace`: the DB file is recreated from scratch.
  - without `--replace`: the loader performs **append-safe ingestion** and skips rows whose `record_key` already exists.
- NDJSON ingestion is performed line-by-line in Python (streaming-safe; no full-file reads in memory).
- Rows are processed in NDJSON file order (deterministic given the same input bytes).

## Expected NDJSON inputs

`--input` is a directory containing canonical NDJSON streams:
- `observations.ndjson` (required)
- `documents.ndjson` (required)
- `medications.ndjson` (optional)
- `conditions.ndjson` (optional)

Each NDJSON line is expected to include:
- `canonical_person_id`, `source`, `source_file`, `event_time`, `run_id`, `record_key`, `schema_version`
- `event_key` may be present for backward compatibility; `record_key` is the canonical dedupe key.

## iOS export inputs (subset mapping)

`healthdelta duckdb build` also accepts an iOS export/staging run directory when `--input` contains:
- `manifest.json`
- `ndjson/observations.ndjson`

In this mode, HealthDelta loads from the `ndjson/` subdirectory and applies a subset mapping into the existing `observations` table:
- `canonical_person_id` → `observations.canonical_person_id`
- `source` → `observations.source`
- `sample_type` → `observations.hk_type`
- `start_time` → `observations.event_time`
- `record_key` → `observations.record_key` (dedupe key)
- `value_num` / `unit` → `observations.value_num` / `observations.unit`
- `run_id` is taken from iOS `manifest.json` `run_id` (applied to all rows)
- `source_file` is set to `ndjson/observations.ndjson` (relative to the iOS export root)

Other streams (documents/medications/conditions) are optional for iOS inputs and may load as empty tables until iOS emits them.

## Schema

All tables include at minimum:
- `schema_version` (INTEGER)
- `record_key` (VARCHAR)
- `canonical_person_id` (VARCHAR)
- `source` (VARCHAR)
- `source_file` (VARCHAR)
- `event_time` (TIMESTAMP)
- `run_id` (VARCHAR)
- `event_key` (VARCHAR)

### `observations`

Additional columns:
- `source_id` (VARCHAR)
- `hk_type` (VARCHAR)
- `resource_type` (VARCHAR)
- `code` (VARCHAR)
- `value` (VARCHAR)
- `value_num` (DOUBLE)
- `unit` (VARCHAR)
- `code_coding_json` (VARCHAR)
- `type_coding_json` (VARCHAR)
- `status` (VARCHAR)

### `documents`

Additional columns:
- `source_id` (VARCHAR)
- `resource_type` (VARCHAR)
- `status` (VARCHAR)
- `type_coding_json` (VARCHAR)

### `medications` (if present)

Additional columns:
- `source_id` (VARCHAR)
- `resource_type` (VARCHAR)
- `status` (VARCHAR)

### `conditions` (if present)

Additional columns:
- `source_id` (VARCHAR)
- `resource_type` (VARCHAR)
- `code` (VARCHAR)
- `code_coding_json` (VARCHAR)

## Privacy / PII

- The DuckDB loader does not add PII fields; it only loads explicit columns from the NDJSON inputs.
- Do not export or query for names, DOB, MRNs, or other patient identifiers; share-safe workflows should use de-identified pipeline outputs before export.
