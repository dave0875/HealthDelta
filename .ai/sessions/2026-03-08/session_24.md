# Session 24 - 2026-03-08

Issue: #191

Goal
- Add canonical NDJSON support for FHIR CarePlan and Goal resources.

Notes
- There is no existing CarePlan or Goal mapping in the exporter, so this slice starts with failing tests.
- Added new canonical NDJSON streams for `Goal` and `CarePlan` rather than overloading an existing stream with a conflicting contract.
- Implemented stable Goal and CarePlan identifiers, status/intent/date fields, and CarePlan-to-Goal linkage via `goal_ids`.
- Added dedicated NDJSON schemas and validator coverage for both new streams.
- Updated the NDJSON runbook to document the Goal and CarePlan field contracts.

Local verification
- `TZ=UTC python3 -m unittest tests/test_ndjson_export.py tests/test_ndjson_validate.py -v`
