# Session 20 - 2026-03-08

Issue: #187

Goal
- Complete the explicit Encounter NDJSON and DuckDB field contract for hospital FHIR exports.

Notes
- Reporting already includes encounter counts by source, so the remaining gap is the Encounter row shape and DuckDB loader schema.
- Starting with failing exporter and DuckDB assertions for encounter identifiers, subject references, and period timestamps.
- Added explicit Encounter row fields for `record_id`, `record_type`, `encounter_id`, `subject_reference`, `period_start`, and `period_end`.
- Extended DuckDB encounter loading/schema to preserve the new fields and support joins on `encounter_id`.
- Adjusted reporting's per-person encounter type query to remain stable after adding the new `record_type` column.
- Updated NDJSON and DuckDB runbooks to document the Encounter field contract.

Local verification
- `TZ=UTC python3 -m unittest tests/test_ndjson_export.py -v`
- `TZ=UTC .venv/bin/python -m unittest tests/test_duckdb.py -v`
- `TZ=UTC .venv/bin/python -m unittest tests/test_reports.py -v`
