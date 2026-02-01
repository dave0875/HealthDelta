# Session 9 — 2026-02-01

Issue: #84

Goal
- Add deterministic share-safe `source_system` provenance tags to exports and reporting surfaces.

Notes
- Added hashed `source_system` tagging in NDJSON export using FHIR `meta.source` or reference identifier systems.
- Added `source_system` persistence through DuckDB tables and report-level source-system coverage CSV.
- Extended NDJSON/report tests to validate tagged output and no raw identifier-system leakage.

Local verification
- TZ=UTC python3 -m unittest tests/test_ndjson_export.py -v
- TZ=UTC python3 -m unittest discover -s tests -v
