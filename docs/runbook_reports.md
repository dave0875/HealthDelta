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
- `coverage.json`: machine-readable clinical coverage summary by stream `resource_type` plus CDA section counts.
- `coverage.md`: human-readable clinical coverage summary with explicit zero-count output when no clinical rows are present.
- `clinical_evidence_manifest.json`: machine-readable share-safe evidence manifest summarizing clinical row counts, mapping coverage, unresolved-reference totals, and redaction status.
- `clinical_evidence_manifest.md`: human-readable share-safe evidence manifest for bundle review.
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
- top record types (derived from existing type/code fields, including medication `resource_type` values such as `MedicationRequest`, `MedicationStatement`, and `MedicationDispense`)

Clinical coverage:
- counts by `resource_type` for each clinical stream present in DuckDB
- observation counts by `code_system`
- CDA section counts using structured fields such as `section_code`, `section_display`, and `section_title`
- zero-count outputs when no clinical rows are present

Evidence manifest:
- total clinical rows across mapped resource types
- per-stream/per-resource-type mapping coverage rows
- unresolved-reference totals
- explicit redaction-status flags confirming payload and identifier exclusions

Unresolved reference audit:
- `summary.json` `reference_integrity.clinical_rows_by_resource_type` breaks unresolved clinical rows down by `resource_type`
- each resource-type row records the deterministic missing reference kind label (for example `Encounter.subject` or `Immunization.patient`)
- `summary.md` includes a `Clinical Unresolved Reference Breakdown` section with the same share-safe counts

## Privacy guarantees and limitations

- Reports only key by `canonical_person_id` and do not include patient names, DOB, MRNs, or raw patient identifiers.
- If future schemas include free-text fields, reports must exclude them by default.
- Record types/codes included in “top record types” are sourced from structured fields like `hk_type`, `resource_type`, and `code`.
