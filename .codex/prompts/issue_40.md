Issue: https://github.com/dave0875/HealthDelta/issues/40

Scope / intent (immutable)
- Document iOS incremental export artifacts and the safe, repeatable workflow for transferring and ingesting them into the Python toolchain.

Acceptance criteria (restated)
- Add `docs/runbook_ios_export.md` covering:
  - where iOS writes outputs
  - what files exist (ndjson, manifest, anchors)
  - how to ingest with Python tooling
  - privacy notes
- Reference it from `AGENTS.md`.
- Record audit artifacts (prompt/session/review/TIME.csv) and close with green CI.

Plan
1) Write `docs/runbook_ios_export.md` (share-safe) describing:
   - iOS sandbox output layout (`Documents/HealthDelta/<run_id>/...`)
   - key artifacts: `ndjson/observations.ndjson`, `manifest.json`, anchor store files
   - transfer guidance (no commits; treat as sensitive)
   - ingestion options:
     - `healthdelta ingest ios ...` (deterministic staging)
     - `healthdelta duckdb build ...` + `healthdelta report build ...`
2) Update `AGENTS.md` to reference the new runbook.
3) Add local issue artifact, session log, review doc, TIME.csv row; close with CI proof.

Constraints
- Repo mutations on Ubuntu host `GORF` only.
- No PII/PHI in documentation.

