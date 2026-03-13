Issue: #241
Date: 2026-03-13

Summary
- Started a repair pass for the doctor's note output after the current summary was reported as clinically useless and dominated by row-count metadata.

Work log
- Opened GitHub issue #241 using the required template.
- Traced the doctor's note path in `healthdelta/note.py`.
- Verified that the current note artifact is a deterministic key-value dump, which explains the poor bedside quality in downstream surfaces.
- Checked the ORIN insight path in `healthdelta/backend_server.py` to confirm which note fields must remain machine-readable.
- Added a failing doctor-note test that requires a human-facing `Summary` section ahead of the raw fact lines.
- Reworked the note generator to emit a deterministic `HealthDelta Doctor's Note` with bedside-style summary bullets plus a machine-readable `Facts` section.
- Tightened the ORIN Ollama prompt so row counts are treated as secondary context rather than the headline.
- Updated the doctor-note runbook to document the new `Summary` + `Facts` contract.

Verification
- `TZ=UTC .venv/bin/python -m unittest tests.test_note -v`
- `TZ=UTC .venv/bin/python -m unittest tests.test_backend_insights_api -v`
- Result: both suites passed.
