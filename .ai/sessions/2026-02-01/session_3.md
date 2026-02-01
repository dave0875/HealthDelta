# Session 3 — 2026-02-01

Issue: #78

Goal
- Resolve canonical person mapping from FHIR subject/patient identifier references.

Notes
- Add deterministic candidate resolution: if multiple mapped people are found, mark unresolved.
- Keep existing fallback to subject reference/default mapping when no identifier mappings are found.

Local verification
- TZ=UTC python3 -m unittest tests/test_ndjson_export.py -v
- TZ=UTC python3 -m unittest discover -s tests -v
