# Session 7 — 2026-02-01

Issue: #82

Goal
- Add versioned NDJSON stream schemas and enforce schema compatibility in validator logic.

Notes
- Added per-stream JSON schema files under `schemas/ndjson/v2/`.
- Validator now resolves stream+version schemas and fails on incompatible schema versions.
- Added tests for schema file presence and invalid schema version detection.

Local verification
- TZ=UTC python3 -m unittest tests/test_ndjson_validate.py -v
- TZ=UTC python3 -m unittest discover -s tests -v
