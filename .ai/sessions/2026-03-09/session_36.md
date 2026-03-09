# Session 36 - 2026-03-09

Issue: #207

Goal
- Add explicit NDJSON validation rules for mapped clinical resource types.

Notes
- Added a clinical-record rulepack to NDJSON validation for Observation, Immunization, Medication, Condition, Allergy, Encounter, and Procedure rows.
- Hardened exporter rows where needed so validation can require stable record identifiers and subject references.
- Added validator tests that cover the new clinical rulepack failures.

Local verification
- `TZ=UTC python3 -m unittest tests/test_ndjson_export.py tests/test_ndjson_validate.py -v`
