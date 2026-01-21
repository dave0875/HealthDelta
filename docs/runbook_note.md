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

`generated_at` is deterministic by design:
- It is set to the maximum `event_time` present in the DB (UTC, ISO-8601 `Z`).
- If no `event_time` values are present, it falls back to `1970-01-01T00:00:00Z`.

## Privacy guarantees and limitations

- Includes only aggregate counts and minimal structured “signals”.
- Does not print:
  - patient names
  - dates of birth
  - free-text clinical notes
  - raw identifiers embedded in fields
- `canonical_person_id` is used only for counting distinct people; IDs are not printed.

