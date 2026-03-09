# Session 26 - 2026-03-08

Issue: #193

Goal
- Add canonical NDJSON support for FHIR Coverage resources.

Notes
- This is an export/validation-only slice; no DuckDB/reporting integration is required by the issue.
- Added a new canonical `coverages.ndjson` stream for FHIR Coverage resources.
- Implemented stable Coverage identifiers, beneficiary subject reference, type/relationship metadata, coverage period, and payor references.
- Added a dedicated NDJSON schema and validator coverage for the new stream.
- Updated the NDJSON runbook to document the Coverage field contract.

Local verification
- `TZ=UTC python3 -m unittest tests/test_ndjson_export.py tests/test_ndjson_validate.py -v`
