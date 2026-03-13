Issue: #242
Date: 2026-03-13

Summary
- Started a deep reprocessing pass from the original Apple export after recent ORIN clinical summaries proved too lossy to describe real recent clinical happenings.

Work log
- Opened GitHub issue #242 using the required template.
- Confirmed the active ORIN cumulative dataset was only a flattened `observations.ndjson` snapshot and not the original Apple export.
- Located the preserved original Apple bootstrap archive at `/opt/healthdelta/data/datasets/dataset_20260312T155255Z_apple_bootstrap/export.zip`.
- Inspected raw FHIR Observation JSON in that archive and verified the source data still contains rich labels such as `code`, `display`, `coding.system`, `resourceType`, and encounter references.
- Compared that with the live ORIN DuckDB and confirmed those recent clinical labels are mostly missing in the current flattened baseline.
- Started an isolated ORIN-side reprocess from the original archive to determine whether the current extraction path already preserves those richer fields or whether a code-path fix is still needed.
- Identified that the first scratch run was consuming the ORIN root filesystem under `/home`, stopped it, and prepared to move the experiment onto the larger `/opt/healthdelta/data` volume.

Verification
- Raw Apple archive inspection confirmed richly labeled `Observation-*.json` members are still present.
- Live ORIN DuckDB inspection confirmed current recent clinical rows are under-labeled, validating the need for deeper reprocessing.
- Added failing regression tests for recent clinical happenings in the doctor note and for ORIN clinical cards when `summary.json` buckets rows too bluntly as `ios`.
- Updated `healthdelta/note.py` so doctor notes now summarize recent 60-day clinical happenings from labeled FHIR observations, including grouped themes and busiest recent clinical days.
- Updated `healthdelta/backend_server.py` so fallback ORIN cards trust richer `doctor_note` source facts when `summary.json` source buckets are too blunt, preserving mixed fitness + clinical context.
- Verified local targeted suites:
  - `TZ=UTC .venv/bin/python -m unittest tests.test_note -v`
  - `TZ=UTC .venv/bin/python -m unittest tests.test_backend_insights_api -v`
- Hot-patched the live ORIN backend container with the same `note.py` and `backend_server.py` changes, regenerated `doctor_note.md` against `/opt/healthdelta/data/datasets/dataset_20260312T155255Z_apple_bootstrap/analysis/duckdb/run.duckdb`, and repointed live `current` back to `dataset_20260312T155255Z_apple_bootstrap`.
- Verified live ORIN now returns the original-export dataset as `current` and surfaces a clinical card with recent themes (`blood counts and differentials`, `serum chemistries`, `blood-bank and transfusion workflow`, `oxygenation monitoring`) plus busiest recent clinical days.
