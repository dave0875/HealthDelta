# Session 34 - 2026-03-09

Issue: #211

Goal
- Add canonical NDJSON support for FHIR Specimen resources.

Notes
- Added a new canonical `specimens.ndjson` stream for FHIR Specimen resources.
- Implemented stable Specimen identifiers plus subject reference, collected/received timing, code fields, and deterministic identifier summaries.
- Added a dedicated NDJSON schema and validator coverage for the new stream.
- Updated the NDJSON runbook to document the Specimen field contract.

Local verification
- `TZ=UTC python3 -m unittest tests/test_ndjson_export.py tests/test_ndjson_validate.py -v`
