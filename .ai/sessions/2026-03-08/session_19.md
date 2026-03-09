# Session 19 - 2026-03-08

Issue: #186

Goal
- Complete immunization and procedure NDJSON field contracts with deterministic missing-field behavior.

Notes
- Starting from the existing baseline that already emits Immunization and Procedure rows with event times but does not expose the full code/display/status contract required by the issue.
- Adding failing exporter assertions first for complete and missing-field examples of each resource type.
- Added immunization and procedure extraction for `code_system`, `code`, `display`, and `status`.
- Added deterministic share-safe warning summary counts for missing immunization/procedure code and status fields.
- Updated the NDJSON runbook to document the Immunization and Procedure field contract and warning summary.

Local verification
- `TZ=UTC python3 -m unittest tests/test_ndjson_export.py -v`
