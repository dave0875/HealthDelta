# Session 31 - 2026-03-09

Issue: #204

Goal
- Add canonical NDJSON support for FHIR Binary resources and share-safe attachment metadata.

Notes
- This is an export/validation-only entity mapping slice.
- Added a new canonical `binaries.ndjson` stream for FHIR Binary resources.
- Preserved share-safe attachment metadata in DocumentReference and DiagnosticReport rows via structured `binary_id` references.
- Added a dedicated NDJSON schema and validator coverage for Binary rows.
- Updated the NDJSON runbook to document Binary handling and attachment redaction rules.

Local verification
- `TZ=UTC python3 -m unittest tests/test_ndjson_export.py tests/test_ndjson_validate.py -v`
