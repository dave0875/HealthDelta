# Session 30 - 2026-03-08

Issue: #203

Goal
- Add canonical NDJSON support for FHIR Provenance resources.

Notes
- This is an export/validation-only entity mapping slice.
- Added a new canonical `provenance.ndjson` stream for FHIR Provenance resources.
- Implemented stable Provenance identifiers plus recorded time, agent references, target references, and resolved target record-key links.
- Added a dedicated NDJSON schema and validator coverage for the new stream.
- Updated the NDJSON runbook to document the Provenance field contract.

Local verification
- `TZ=UTC python3 -m unittest tests/test_ndjson_export.py tests/test_ndjson_validate.py -v`
