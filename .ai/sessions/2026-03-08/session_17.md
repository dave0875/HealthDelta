# Session 17 - 2026-03-08

Issue: #184

Goal
- Complete the Condition mapping contract in canonical NDJSON, including deterministic missing-field handling and a share-safe warning summary.

Notes
- Existing exporter already routes `Condition` rows to `conditions.ndjson`, but it did not yet expose the field set required by the issue.
- Added Condition field extraction for `code_system`, `code`, `display`, `clinical_status`, `verification_status`, and `onset_time`.
- Added deterministic share-safe warning summary counts for missing Condition code/status fields.
- Updated the NDJSON runbook to document the new Condition mapping fields and warning summary.

Local verification
- `TZ=UTC python3 -m unittest tests/test_ndjson_export.py -v`
