# Session 24 — 2026-01-21

Issues worked
- #24 Operator: persistent identity across runs (stable `canonical_person_id`)

Execution environment
- Repository mutations executed on Ubuntu host: `GORF`

Work summary
- Updated operator command to store identity under `<base_out>/state/identity` to persist canonical identity across runs.
- Updated NDJSON exporter identity discovery to find identity in state for operator runs.
- Updated operator integration tests to:
  - expect identity under state
  - prove stable `canonical_person_id` across two runs with the same name but different patient IDs
- Updated `docs/runbook_operator.md` to document identity persistence and share-safety implications.
- Recorded immutable prompt: `.codex/prompts/issue_24.md`
- Added local issue artifact: `docs/issues/ISSUE-0024.md`

Local verification
- `python3 -m unittest discover -s tests -p 'test_*.py'` (pass; DuckDB-dependent tests may skip locally)

Review
- Wrote AI-on-AI review notes: `docs/reviews/2026-01-21_24.md`

CI evidence
- Pending: push Issue #24 changes and record the green CI run URL (Linux + macOS with `ios-xcresult` artifact) before closing.

