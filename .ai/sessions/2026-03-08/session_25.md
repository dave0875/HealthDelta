# Session 25 - 2026-03-08

Issue: #192

Goal
- Add canonical NDJSON support for FHIR ServiceRequest resources.

Notes
- This is another export/validation-only slice; there is no existing ServiceRequest mapping in the exporter.
- Added a new canonical `service_requests.ndjson` stream for ServiceRequest resources.
- Implemented stable ServiceRequest identifiers, subject reference, status, intent, authored date, coding metadata, and performer references.
- Added a dedicated NDJSON schema and validator coverage for the new stream.
- Updated the NDJSON runbook to document the ServiceRequest field contract.

Local verification
- `TZ=UTC python3 -m unittest tests/test_ndjson_export.py tests/test_ndjson_validate.py -v`
