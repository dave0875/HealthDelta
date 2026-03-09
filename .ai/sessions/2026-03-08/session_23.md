# Session 23 - 2026-03-08

Issue: #190

Goal
- Complete the explicit DocumentReference NDJSON field contract and share-safe attachment metadata handling.

Notes
- The existing DocumentReference export is minimal and does not yet expose the stable identifier, subject, and attachment metadata contract required by the issue.
- Added explicit DocumentReference row fields for identifiers, subject reference, type-system metadata, and share-safe attachment summaries.
- Tightened `documents.schema.json` so NDJSON validation now enforces the DocumentReference contract instead of accepting generic base fields only.
- Updated the NDJSON runbook to document the DocumentReference field contract and attachment redaction rules.

Local verification
- `TZ=UTC python3 -m unittest tests/test_ndjson_export.py tests/test_ndjson_validate.py -v`
