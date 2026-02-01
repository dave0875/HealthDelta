# Session 1 — 2026-02-01

Issue: #76

Goal
- Export MedicationStatement/MedicationDispense NDJSON and cover in tests.

Notes
- Add event_time handling and include new resource types in medications stream.

Local verification
- TZ=UTC python3 -m unittest tests/test_ndjson_export.py -v
