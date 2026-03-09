# Session 27 - 2026-03-08

Issue: #200

Goal
- Add canonical NDJSON support for FHIR Organization resources.

Notes
- This is an export/validation-only entity mapping slice.
- Added a new canonical `organizations.ndjson` stream for Organization resources.
- Implemented stable Organization identifiers plus name, type, and address fields.
- Added a dedicated NDJSON schema and validator coverage for the new stream.
- Updated the NDJSON runbook to document the Organization field contract.

Local verification
- `TZ=UTC python3 -m unittest tests/test_ndjson_export.py tests/test_ndjson_validate.py -v`
