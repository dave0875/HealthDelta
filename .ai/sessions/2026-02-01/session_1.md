# Session 1 — 2026-02-01

Issue: #77

Goal
- Export AllergyIntolerance and Immunization resources in canonical NDJSON.

Notes
- Extend FHIR event_time logic and NDJSON export tests.

Local verification
- TZ=UTC python3 -m unittest tests/test_ndjson_export.py -v
- TZ=UTC python3 -m unittest discover -s tests -v
