# Session 1 - 2026-02-02

Issue: #121

Goal
- Add deterministic export schema + sensitive-field profiling artifacts and CI evidence uploads.

Notes
- Extended `healthdelta export profile` outputs with `clinical_schema_keys.csv` and `sensitive_field_map.json`.
- Added Linux CI profile smoke step and artifact uploads for profile evidence.
- Updated profile runbook with the new share-safe outputs.

Local verification
- TZ=UTC python3 -m unittest tests/test_profile.py -v
- TZ=UTC python3 -m unittest tests/test_audit_artifacts.py -v
- TZ=UTC python3 -m unittest discover -s tests -v
