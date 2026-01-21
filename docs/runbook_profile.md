# Runbook: Export Profiling (`healthdelta export profile`)

This runbook describes how to generate a fast, deterministic, share-safe profile of an unpacked Apple Health export directory.

## When to use

Run this as the first step on a new export directory to understand scale and structure (counts, file sizes, schema-level types) before running ingest/pipeline.

## Command

```bash
healthdelta export profile --input <export_dir> --out <dir> [--sample-json N] [--top-files K]
```

Defaults:
- `--sample-json 200` (deterministically scans the first N JSON files, sorted by relative path)
- `--top-files 20`

Notes:
- This command is directory-only for now (does not profile `export.zip`).
- It is designed to be streaming-safe for multi-GB `export.xml` and `export_cda.xml` (no full DOM parse).

## Outputs (all share-safe)

Written under `--out`:
- `profile.json`: machine-readable summary.
- `profile.md`: human-readable one-screen summary + sections.
- `files_top.csv`: largest files (size + relative path).
- `counts_by_ext.csv`: file extension counts.
- `healthkit_record_types.csv`: HealthKit `Record` `type=` counts (when `export.xml` exists).
- `clinical_resource_types.csv`: FHIR `resourceType` counts from clinical JSON (when `clinical-records/*.json` exists).
- `cda_tag_counts.csv`: CDA tag name counts (top N only) from `export_cda.xml` when present.

## Privacy guarantees and limits

This profile output must not include:
- names, DOB, identifiers, addresses, phone/email
- free-text clinical note contents or raw payload fragments
- absolute paths or directory names outside the export root
- event timestamps extracted from payloads

Allowed outputs are limited to:
- relative file paths within the export root
- file sizes and aggregate counts
- schema-level strings:
  - HealthKit `Record` `type=` values
  - FHIR `resourceType` values
  - CDA tag names (local names only)

