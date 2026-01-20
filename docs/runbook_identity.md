# Identity Runbook (Bootstrap Person Registry)

## Goal
Build a canonical person registry and observed alias/provenance records from staged data, using an explicit, testable name parsing + matching rule.

## Command
From the repo root:

- `healthdelta identity build --input data/staging/<run_id>`

## Inputs
The `--input` path must be a staging run directory produced by `healthdelta ingest` (Issue #4), and must include `layout.json`.

## Outputs
Writes:
- `data/identity/people.json`
- `data/identity/aliases.json`

## Matching rule (initial)
Two records are treated as the same person only if BOTH first name and last name match after normalization.

Normalization:
- trim
- collapse whitespace
- casefold

Name parsing:
- `"First Last"` → first token + last token
- `"Last, First"` → token before comma + first token after comma
- Middle names/initials are ignored for now (by construction).

## Provenance / append-only behavior
Observed external IDs and source references are appended to `aliases.json` with a stable `alias_key` to avoid re-adding identical observations on re-run.

