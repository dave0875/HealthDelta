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

- The loader **requires `--replace`** to overwrite an existing database file.
  - If `--db` already exists and `--replace` is not set, the command errors.
- NDJSON ingestion is performed by DuckDB’s JSON reader for newline-delimited JSON, avoiding full-file loads in Python.
- Rows are inserted using a deterministic `ORDER BY` during ingestion to promote repeatability.

## Expected NDJSON inputs

`--input` is a directory containing canonical NDJSON streams:
- `observations.ndjson` (required)
- `documents.ndjson` (required)
- `medications.ndjson` (optional)
- `conditions.ndjson` (optional)

Each NDJSON line is expected to include:
- `canonical_person_id`, `source`, `source_file`, `event_time`, `run_id`, `event_key`

## Schema

All tables include at minimum:
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

