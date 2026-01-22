Issue: https://github.com/dave0875/HealthDelta/issues/36

Scope / intent (immutable)
- Emit a deterministic `manifest.json` alongside iOS NDJSON exports so integrity and basic counts can be validated without rescanning NDJSON payloads.

Acceptance criteria (restated)
- Emit `manifest.json` next to NDJSON outputs containing:
  - `run_id`
  - file list with sizes + sha256
  - row counts per stream
- Determinism: same NDJSON bytes => byte-stable `manifest.json`.
- Unit tests verify deterministic manifest bytes across reruns.
- Record audit artifacts (prompt/session/review/TIME.csv) and close with green CI (macOS `ios-xcresult` artifact).

Design notes
- Manifest location: `Documents/HealthDelta/<run_id>/manifest.json` (in the run directory, next to the `ndjson/` folder).
- Manifest content is derived only from run_id and exported file bytes (size + sha256 + newline-delimited row counts).
- Stable ordering: file entries sorted by relative path; JSON serialized with sorted keys.
- No timestamps or environment-specific fields (to preserve byte stability).

Plan
1) Add `IOSExportManifest` builder/writer in Swift (CryptoKit sha256; count rows by counting newlines).
2) Extend `IOSExportLayout` to include `manifestURL(runID:)` and a helper to list expected NDJSON stream files (currently observations only).
3) Unit tests:
   - build a tiny synthetic observations NDJSON file
   - write manifest twice and assert identical bytes
   - assert expected fields (run_id, sha256, size_bytes, row_counts)
4) Wire manifest emission into a small helper API that operators/UI can call later (no UI in this issue).
5) CI proof + audit artifacts.

Constraints
- Repo mutations on Ubuntu host `GORF` only; Xcode execution only via GitHub Actions self-hosted macOS runner.
- Synthetic-only tests.

