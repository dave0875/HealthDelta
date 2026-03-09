# Session 22 - 2026-03-08

Issue: #189

Goal
- Complete the explicit DiagnosticReport NDJSON field contract and validation evidence.

Notes
- DiagnosticReport rows already exist in minimal form, so this slice is expected to focus on explicit identifiers, subject references, and validation proof rather than introducing a new stream.
- Added explicit DiagnosticReport row fields for identifiers, subject reference, effective start/end timestamps, code-system metadata, and stable result observation link keys.
- Tightened `diagnostic_reports.schema.json` so NDJSON validation now enforces the DiagnosticReport contract instead of accepting generic base fields only.
- Updated the NDJSON runbook to document the DiagnosticReport field contract.

Local verification
- `TZ=UTC python3 -m unittest tests/test_ndjson_export.py tests/test_ndjson_validate.py -v`
