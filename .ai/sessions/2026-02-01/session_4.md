# Session 4 — 2026-02-01

Issue: #79

Goal
- Add unresolved reference integrity reporting to share-safe report artifacts.

Notes
- Added deterministic unresolved counts by `reference_type` and surfaced them in both CSV and summary outputs.
- Added test fixture for mixed resolved/unresolved rows (Encounter/Procedure/Immunization) to validate counts.

Local verification
- TZ=UTC python3 -m unittest discover -s tests -v
