# Session 18 - 2026-03-08

Issue: #185

Goal
- Complete medication and allergy NDJSON field contracts with deterministic missing-field behavior.

Notes
- Medication and allergy rows already export to canonical streams, but they do not yet expose the code/display field contract required by the issue.
- Starting with failing exporter assertions for complete medication/allergy examples plus missing-field examples.
- Added medication and allergy field extraction for `code_system`, `code`, `display`, and `status`.
- Added deterministic share-safe warning summary counts for missing medication/allergy code/status fields.
- Updated the NDJSON runbook to document the medication/allergy field contract and warning summary.

Local verification
- `TZ=UTC python3 -m unittest tests/test_ndjson_export.py -v`
