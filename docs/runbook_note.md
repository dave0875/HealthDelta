# Runbook: Doctor’s Note (`healthdelta note`)

This runbook describes how to generate a deterministic, share-safe “doctor’s note” one-screen summary from a DuckDB database.

## Command

Build the doctor note artifacts:

```bash
healthdelta note build --db <path> --out <dir> [--mode local|share]
```

Notes:
- This is a share-safe summary intended for quick copy/paste sharing.
- It is non-diagnostic and contains no names, DOB, or free-text identifiers.
- The note now uses a two-part structure:
  - `Summary`: a short clinician-style overview of scope, dominant signals, and limits
  - `Facts`: deterministic machine-readable lines used by downstream ORIN refinement
- When the DB contains sufficiently rich recent FHIR observation labels, the `Summary` also adds a deterministic recent-clinical-happenings block:
  - share-safe patient-bucket count and active-day count over the latest 60-day clinical window
  - grouped recent clinical themes such as oxygenation monitoring, blood counts, chemistries, or transfusion workflow
  - busiest recent clinical days by row volume

## Outputs

Written under `--out`:
- `doctor_note.txt`
- `doctor_note.md`

Both outputs are currently identical plain text (the `.md` file is valid Markdown as-is).

## Determinism

Outputs are byte-stable for the same DB:
- Stable line ordering and formatting
- Newline-terminated files
- No wall-clock timestamps
- Human-facing summary text is still deterministic because it is derived only from ordered DuckDB aggregates

`generated_at` is deterministic by design:
- It is set to the maximum `event_time` present in the DB (UTC, ISO-8601 `Z`).
- If no `event_time` values are present, it falls back to `1970-01-01T00:00:00Z`.

## Privacy guarantees and limitations

- Includes only share-safe aggregate counts and structured signal labels.
- Does not print:
  - patient names
  - dates of birth
  - free-text clinical notes
  - raw identifiers embedded in fields
- `canonical_person_id` is used only for counting distinct people; IDs are not printed.
- Row counts remain available in the `Facts` section for scope/confidence, but the note is intended to foreground health meaning rather than operational volume.
- Recent clinical theme grouping is deterministic and vocabulary-based; it summarizes only labeled structured observations already present in the DB and does not invent diagnoses or treatment conclusions.
