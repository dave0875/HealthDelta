# Session 2 — 2026-02-01

Issue: #75

Goal
- Export DiagnosticReport NDJSON with Observation linkage.

Notes
- Add DiagnosticReport stream, link to Observations when references resolve.

Local verification
- TZ=UTC python3 -m unittest tests/test_ndjson_export.py -v
