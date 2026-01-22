Issue: https://github.com/dave0875/HealthDelta/issues/35

Scope / intent (immutable)
- Add a deterministic on-disk export layout for iOS NDJSON outputs under the app sandbox.
- Ensure iOS exporter/tests use stable filenames and do not mutate outputs when unchanged.

Acceptance criteria (restated)
- Provide an iOS output layout convention under the app sandbox:
  - `Documents/HealthDelta/<run_id>/ndjson/observations.ndjson`
- Ensure writes are deterministic and atomic (best-effort for file creation).
- Unit tests verify:
  - output paths are deterministic for a fixed `run_id`
  - repeated runs do not mutate files when unchanged
- Record audit artifacts (prompt/session/review/TIME.csv) and close with green CI (macOS `ios-xcresult` artifact).

Plan
1) Add `IOSExportLayout` (pure path builder + directory creation helper) with a test-injectable base directory and a default `Documents/HealthDelta` base.
2) Update iOS exporter tests to compute `outputURL` from the layout and assert deterministic paths.
3) Improve `NDJSONWriter.appendLines` to ensure parent directories exist and to use atomic file creation when the destination does not yet exist.
4) CI proof + audit artifacts.

Constraints
- Repo mutations on Ubuntu host `GORF` only; Xcode execution only via GitHub Actions self-hosted macOS runner.
- Synthetic-only test data.

