# Session 21 — 2026-01-21

Issues worked
- #21 Share bundle: package share-safe artifacts for collaboration

Execution environment
- Repository mutations executed on Ubuntu host: `GORF`

Work summary
- Added `healthdelta share bundle --run <base_out>/<run_id> --out <path>.tar.gz` to package share-safe artifacts only:
  - allowlist: `deid/`, `ndjson/`, `duckdb/`, `reports/`, `note/`
  - includes `registry/run_entry.json` derived from the local run registry (excluding free-text notes)
  - excludes `staging/` and `identity/` by design
- Implemented deterministic tar.gz generation:
  - stable member ordering (sorted by archive path)
  - normalized tar metadata (mtime/uid/gid/uname/gname)
  - normalized gzip header (`mtime=0`, empty filename)
- Added synthetic test that verifies:
  - `staging/` and `identity/` are excluded
  - banned tokens from staging/notes do not appear in the bundle
  - repeated bundle generation is byte-stable
- Added runbook: `docs/runbook_share_bundle.md` and referenced it from `AGENTS.md`.
- Added local issue artifact: `docs/issues/ISSUE-0021.md`
- Recorded immutable prompt: `.codex/prompts/issue_21.md`

Local verification
- `python3 -m unittest discover -s tests -p 'test_*.py'` (pass; DuckDB-dependent tests may skip locally)

Review
- Wrote AI-on-AI review notes: `docs/reviews/2026-01-21_21.md`

CI evidence
- GitHub Actions run: https://github.com/dave0875/HealthDelta/actions/runs/21213394118 (Linux tests + macOS Xcode job); artifact: `ios-xcresult`.
