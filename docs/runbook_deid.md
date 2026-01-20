# De-identification Runbook (Share-safe Dataset)

## Goal
Produce a parallel, share-safe copy of a staged export while preserving the export’s overall structure and producing deterministic artifacts for debugging/collaboration.

## Command

- `healthdelta deid --input data/staging/<run_id> --identity data/identity --out data/deid/<run_id>/`

## Inputs
- `--input`: a staging run directory produced by `healthdelta ingest` (must contain `layout.json`)
- `--identity`: an identity directory produced by `healthdelta identity build` (must contain `people.json`)

## Outputs
Under `--out`:
- `manifest.json` (hashes/sizes for output files; paths redacted)
- `layout.json` (where de-identified assets were written)
- `mapping.json` (canonical_person_id -> `Patient N` only)
- De-identified copies (if present in staging):
  - `export.xml`
  - `export_cda.xml`
  - clinical JSON files listed in `layout.json`

## Determinism
- Patient numbering is derived deterministically from `people.json` content (sorted by last_norm/first_norm/person_key).
- Output file content is deterministic for the same `--input` bytes and the same `people.json` bytes.
- `manifest.json.timestamps.*` are time-varying by design.

## MVP de-id coverage (explicit)
- Name replacement: replaces known names matching `First Last` and `Last, First` with `Patient N` (case-insensitive, whitespace tolerant).
- CDA: overwrites `patientRole/patient/name` and replaces `birthTime/@value` with `19000101`.
- FHIR JSON: minimal rewrite of `Patient.name` fields, sets `Patient.birthDate` to `1900-01-01` if present, and runs a string replacement pass over string values.

## Not covered yet
- Full FHIR-wide field scrubbing.
- Comprehensive identifier redaction across all resources/fields.
- Free-text PII outside targeted replacements.
