# Session 32 - 2026-03-09

Issue: #206

Goal
- Add a share-safe clinical records fixture pack and wire at least one mapping test to use it.

Notes
- Added `tests/fixtures/clinical_records_v1` with a README and synthetic FHIR resource files.
- Updated NDJSON export tests to exercise the new fixture pack directly.

Local verification
- `TZ=UTC python3 -m unittest tests/test_ndjson_export.py -v`
