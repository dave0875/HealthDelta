# Session 33 - 2026-03-09

Issue: #210

Goal
- Add canonical NDJSON support for FHIR ImagingStudy resources.

Notes
- Added a new canonical `imaging_studies.ndjson` stream for FHIR ImagingStudy resources.
- Implemented stable ImagingStudy identifiers plus subject reference, started time, and a deterministic share-safe series summary.
- Added a dedicated NDJSON schema and validator coverage for the new stream.
- Updated the NDJSON runbook to document the ImagingStudy field contract.

Local verification
- `TZ=UTC python3 -m unittest tests/test_ndjson_export.py tests/test_ndjson_validate.py -v`
