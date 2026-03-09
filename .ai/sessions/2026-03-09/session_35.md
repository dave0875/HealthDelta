# Session 35 - 2026-03-09

Issue: #212

Goal
- Add canonical NDJSON support for FHIR Device resources.

Notes
- Added a new canonical `devices.ndjson` stream for FHIR Device resources.
- Implemented stable Device identifiers plus patient reference, status, type fields, manufacturer, and deterministic identifier summaries.
- Added a dedicated NDJSON schema and validator coverage for the new stream.
- Updated the NDJSON runbook to document the Device field contract.

Local verification
- `TZ=UTC python3 -m unittest tests/test_ndjson_export.py tests/test_ndjson_validate.py -v`
