# Runbook: Share-safe Reporting (`healthdelta report`)

This runbook describes how to generate deterministic, share-safe summary artifacts from a DuckDB database built by Issue #9.

## Command

Build report artifacts:

```bash
healthdelta report build --db <path> --out <dir> [--mode local|share]
```

Optional terminal summary:

```bash
healthdelta report show --db <path>
```

Notes:
- Commands are headless and operate on local files only.
- Reports are always share-safe (no names/DOB/free-text patient identifiers). `--mode` is reserved for future strictness.

## Output artifacts (`report build`)

Written under `--out`:
- `summary.json`: machine-readable report summary (stable JSON).
- `summary.md`: human-readable summary (stable Markdown).
- `coverage_by_person.csv`: rows per stream per `canonical_person_id`, plus min/max `event_time` across tables.
- `coverage_by_source.csv`: counts by `(stream, source)` for all tables.
- `timeline_daily_counts.csv`: daily counts by `(day, stream, source)` for rows with non-null `event_time`.

All files are written deterministically:
- stable ordering and formatting
- newline-terminated
- no non-deterministic “generated_at” timestamps

## What’s included (minimum)

From available DuckDB tables (`observations`, `documents`, optionally `medications`/`conditions`):

Global (per table):
- total rows
- distinct `canonical_person_id`
- min/max `event_time` (when present)
- rows by `source` (`healthkit`/`fhir`/`cda`)

Per person:
- rows per table
- min/max `event_time` across all tables (when present)
- top record types (derived from existing type/code fields)

## Privacy guarantees and limitations

- Reports only key by `canonical_person_id` and do not include patient names, DOB, MRNs, or raw patient identifiers.
- If future schemas include free-text fields, reports must exclude them by default.
- Record types/codes included in “top record types” are sourced from structured fields like `hk_type`, `resource_type`, and `code`.

