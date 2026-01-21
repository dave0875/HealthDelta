# Runbook: NDJSON validation (`healthdelta export validate`)

Purpose: provide a fast, deterministic validator for HealthDelta’s canonical NDJSON streams, including optional share-safe guardrails for synthetic test fixtures.

## Command

Validate all `*.ndjson` files under an NDJSON output directory:

`healthdelta export validate --input <ndjson_dir>`

Optional (test-fixture guardrails):

- `--banned-token <token>` (repeatable)
- `--banned-regex <pattern>` (repeatable)

## What it checks

- Every `*.ndjson` file under `--input` is read line-by-line (streaming-safe).
- Each non-empty line must be valid JSON and must be a JSON object.
- Each record must include (and use string values for):
  - `canonical_person_id`
  - `source`
  - `source_file`
  - `event_time`
  - `run_id`
- Files must be newline-terminated (no partial final line).

## Output + exit codes

- On success: prints `ok` and exits `0`.
- On validation failure: prints deterministic `ERROR <file>:<line> <code> <message>` lines to stderr and exits `1`.

## Privacy notes

This validator does not attempt to “discover” PII. The banned token/pattern options exist to enforce expectations in synthetic tests (e.g., ensuring known synthetic names/DOBs do not appear in outputs).

