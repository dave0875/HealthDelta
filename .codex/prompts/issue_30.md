Issue: https://github.com/dave0875/HealthDelta/issues/30

Scope / intent (immutable)
- Add a small, tested iOS anchor persistence module for HealthKit anchored queries.
- Provide deterministic, file-backed save/load keyed by a stable string key.
- Include minimal migration/versioning and graceful handling of missing/corrupt files.

Acceptance criteria (restated)
- Add an iOS Swift module that:
  - stores anchors by key to the app sandbox
  - uses deterministic serialization
  - supports minimal migration/versioning
- Add unit tests in `ios/HealthDelta/Tests` verifying:
  - save/load roundtrip
  - stable bytes for same anchor input
  - missing/corrupt files handled gracefully
- No PHI/PII logging.
- CI green required before closing (macOS Xcode job uploads `ios-xcresult`).

Design choices
- Storage format: deterministic binary envelope:
  - magic bytes + version byte + `NSKeyedArchiver` payload for `HKQueryAnchor` (secure coding).
- Filenames: `sha256(<key>) + ".bin"` to avoid leaking key material and to keep filesystem-safe.
- API shape: `AnchorStore` with injected directory URL for testability (use temp dirs in tests).

Plan
1) Update `ios/HealthDelta/project.yml` to link `HealthKit.framework`.
2) Add `ios/HealthDelta/Sources/AnchorStore.swift` implementing:
   - save/load/delete by key
   - deterministic serialization helpers
   - versioned decode with graceful failure
3) Add `ios/HealthDelta/Tests/AnchorStoreTests.swift` covering AC.
4) Record audit artifacts (session log, review, TIME.csv) and close with CI proof.

Execution constraints
- Repo mutations on Ubuntu host `GORF` only.
- Xcode compilation/testing only via GitHub Actions self-hosted macOS runner.
