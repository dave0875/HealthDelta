# Session 25 — 2026-01-21

Issues worked
- #25 NDJSON schema: add `schema_version` + stable `record_key`

Execution environment
- Repository mutations executed on Ubuntu host: `GORF`

Work summary
- Updated NDJSON exporter to emit `schema_version` and `record_key` on every record (with `record_key` aligned to existing `event_key`).
- Updated NDJSON validator to require `schema_version` (int) and `record_key` (string).
- Updated docs: `docs/runbook_ndjson.md` to document the new fields.
- Updated synthetic tests for exporter + validator to assert presence/types.
- Recorded immutable prompt: `.codex/prompts/issue_25.md`
- Added local issue artifact: `docs/issues/ISSUE-0025.md`

Local verification
- `python3 -m unittest discover -s tests -p 'test_*.py'` (pass; DuckDB-dependent tests may skip locally)

Review
- Wrote AI-on-AI review notes: `docs/reviews/2026-01-21_25.md`

CI evidence
- Green CI: https://github.com/dave0875/HealthDelta/actions/runs/21232381130 (Linux + macOS with `ios-xcresult` artifact).
