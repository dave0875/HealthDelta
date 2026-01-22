Issue: https://github.com/dave0875/HealthDelta/issues/37

Scope / intent (immutable)
- Add a deterministic Python ingestion path for iOS-exported NDJSON artifacts so they can be analyzed with the existing Python toolchain without requiring an Apple Health export.zip.

Acceptance criteria (restated)
- Add `healthdelta ingest ios --input <dir> --out <staging_dir>`.
- Validate required inputs, copy into deterministic staging layout, and write a staging manifest.
- Synthetic tests only.
- Record audit artifacts (prompt/session/review/TIME.csv) and close with green CI.

Design notes
- Input expectation: iOS export run directory (copied from device) containing:
  - `manifest.json`
  - `ndjson/observations.ndjson`
- Output: a staging run directory under `--out/<run_id>/` containing:
  - `manifest.json` (staging manifest; deterministic; no absolute paths)
  - `source/ios/manifest.json` (copied from input)
  - `ndjson/observations.ndjson` (copied from input)
- Deterministic `run_id` derivation: sha256 over stable relative paths + sha256(file bytes) for required files.
- No timestamps in the staging manifest (to keep byte stability).

Plan
1) Add `ingest_ios_to_staging` in `healthdelta/ingest.py` and wire CLI routing for `healthdelta ingest ios ...` while keeping existing `healthdelta ingest --input ...` behavior.
2) Add synthetic tests that:
   - build a tiny fake iOS export directory
   - run the CLI
   - assert output layout and deterministic `manifest.json` bytes across reruns
3) Add required local artifacts (docs/issues, session log, review, TIME.csv) and close with CI proof.

Constraints
- Repo mutations on Ubuntu host `GORF` only.
- No PHI/PII in fixtures or logs.

