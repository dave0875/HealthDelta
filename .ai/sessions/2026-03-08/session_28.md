# Session 28 - 2026-03-08

Issue: #201

Goal
- Add canonical NDJSON support for FHIR Practitioner resources.

Notes
- This is an export/validation-only entity mapping slice.
- Added a new canonical `practitioners.ndjson` stream for Practitioner resources.
- Implemented stable Practitioner identifiers plus display name and a structured identifier pair.
- Added a dedicated NDJSON schema and validator coverage for the new stream.
- Updated the NDJSON runbook to document the Practitioner field contract.

Local verification
- `TZ=UTC python3 -m unittest tests/test_ndjson_export.py tests/test_ndjson_validate.py -v`
