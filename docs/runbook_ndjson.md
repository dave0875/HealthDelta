# Runbook: Canonical NDJSON Export (`healthdelta export ndjson`)

This runbook defines how HealthDelta exports canonical, share-safe NDJSON streams from pipeline outputs.

## Command

```bash
healthdelta export ndjson --input <pipeline_run_dir> --out <dir> [--mode local|share]
```

Inputs:
- `--mode local`: `--input` must be a staging run directory like `data/staging/<run_id>`.
- `--mode share`: `--input` should be a de-id run directory like `data/deid/<run_id>` (share-safe).

The exporter never uploads data; it reads local files only.

## Output files

Written under `--out`:
- `observations.ndjson` (always)
- `documents.ndjson` (always)
- `medications.ndjson` (only if MedicationRequest records are present)
- `conditions.ndjson` (only if Condition records are present)

NDJSON is one JSON object per line (newline-terminated).

## Common schema (all streams)

Every emitted line includes:
- `canonical_person_id`: canonical person key (UUID string) when resolvable; otherwise the literal `"unresolved"`.
- `source`: `"healthkit"` | `"fhir"` | `"cda"`.
- `source_file`: relative, redacted path within the run directory (never an absolute host path).
- `event_time`: best-available timestamp as an ISO-8601 string (UTC `...Z`) when parseable; otherwise `null` or an unparsed string.
- `run_id`: the pipeline/staging run id.

Fields that MUST NOT appear in NDJSON:
- names
- dates of birth
- free-text patient identifiers (MRNs, raw patient IDs, etc.)

## Source handling

### HealthKit XML (`export.xml`)
- Stream-parses `<Record>` elements and emits them as observation rows.
- `event_time` selection: prefer `startDate`, otherwise `endDate`.

### FHIR JSON (`clinical-records/*.json`)
- Treats each file as a single resource (not Bundles).
- Exports only:
  - `Observation` → `observations.ndjson`
  - `DocumentReference` → `documents.ndjson`
  - `MedicationRequest` → `medications.ndjson`
  - `Condition` → `conditions.ndjson`
- `Patient` resources are used for identity resolution only and are not exported.
- `canonical_person_id` resolution:
  - preferred: `subject.reference == "Patient/<id>"` matched against identity aliases (`fhir:id`)
  - fallback: if exactly one person exists in `data/identity/people.json`, use that person
  - otherwise: `"unresolved"`

### CDA XML (`export_cda.xml`)
- Stream-parses `<observation>` elements and emits minimal observation-like rows when available:
  - `effectiveTime@value` → `event_time` (parsed as UTC when format is `YYYYMMDDHHMMSS`)
  - `code@code`
  - `value@value` / `value@unit`
- Skipped (MVP): narrative text, full section semantics, non-observation entries, and any attempt at comprehensive CDA coverage.

## Determinism rules

The exporter is deterministic for the same input + identity + mode:
- Per-record `event_key` is derived from a stable JSON payload (sha256) and used to dedupe within a run.
- Per-stream ordering is a stable sort by:
  - `event_time`, `canonical_person_id`, `source`, `source_file`, `source_id`, `event_key`
- Per-line JSON serialization uses:
  - sorted keys (`sort_keys=True`)
  - stable separators (`separators=(",", ":")`)
- Outputs are written via a temp file and atomically replaced.
