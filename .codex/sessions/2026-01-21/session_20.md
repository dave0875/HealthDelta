# Session 20 — 2026-01-21

Issues worked
- #20 NDJSON validation: schema checks + share-safe assertions

Execution environment
- Repository mutations executed on Ubuntu host: `GORF`

Work summary
- Added `healthdelta export validate --input <ndjson_dir>`:
  - streaming-safe line-by-line NDJSON validation
  - baseline required key checks (`canonical_person_id`, `source`, `source_file`, `event_time`, `run_id`)
  - optional banned token/pattern assertions for synthetic test fixtures (`--banned-token`, `--banned-regex`)
- Added synthetic tests covering passing and failing cases.
- Added runbook: `docs/runbook_ndjson_validate.md` and referenced it from `AGENTS.md`.
- Added local issue artifact: `docs/issues/ISSUE-0020.md`
- Recorded immutable prompt: `.codex/prompts/issue_20.md`

Local verification
- `python3 -m unittest discover -s tests -p 'test_*.py'` (pass; DuckDB-dependent tests may skip locally)

Review
- Wrote AI-on-AI review notes: `docs/reviews/2026-01-21_20.md`

CI evidence
- GitHub Actions run: https://github.com/dave0875/HealthDelta/actions/runs/21213152423 (Linux tests + macOS Xcode job); artifact: `ios-xcresult`.
