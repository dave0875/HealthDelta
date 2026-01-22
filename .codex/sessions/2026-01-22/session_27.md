# Session 27 — 2026-01-22

Issues worked
- #27 Share bundle: add `share verify` (allowlist + hashes)

Execution environment
- Repository mutations executed on Ubuntu host: `GORF`

Work summary
- Extended `healthdelta share bundle` to include `registry/bundle_manifest.csv` with `path,size,sha256` for all archived regular files (excluding the manifest itself).
- Added `healthdelta share verify --bundle <path>.tar.gz` to enforce allowlist-only members, validate `registry/run_entry.json`, and validate manifest size/hash for each file.
- Updated `docs/runbook_share_bundle.md` with verification usage.
- Added synthetic tests for a passing bundle and a failing bundle with disallowed paths.

Local verification
- `python3 -m unittest discover -s tests -p 'test_*.py'` (pass; DuckDB-dependent tests may skip locally)

AI-on-AI review
- Local model: `ollama run llama3.1:8b` (see `docs/reviews/2026-01-22_27.md`)

CI evidence
- Green CI: https://github.com/dave0875/HealthDelta/actions/runs/21232757417 (Linux + macOS with `ios-xcresult` artifact).

