# Session 14 - 2026-03-08

Issue: #181

Goal
- Add a clinical-record-specific unresolved-reference section to the reporting outputs.

Notes
- Confirmed there was no existing prompt/session history for Issue #181.
- Reusing the existing unresolved canonical-person audit path instead of introducing new identity logic.
- Starting with report-test coverage that requires a deterministic clinical unresolved-reference section in the summary outputs.
- Added `reference_integrity.clinical_rows_by_resource_type` to `summary.json` and a matching `Clinical Unresolved Reference Breakdown` section to `summary.md`.
- Updated `docs/runbook_reports.md` to document the new clinical unresolved-reference section.

Local verification
- `TZ=UTC .venv/bin/python -m unittest tests/test_reports.py -v`
