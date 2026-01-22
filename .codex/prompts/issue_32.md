Issue: https://github.com/dave0875/HealthDelta/issues/32

Scope / intent (immutable)
- Add a deterministic NDJSON writer component in Swift.
- Integrate it with the existing anchor store (Issue #30) and anchored query abstraction (Issue #31) to simulate incremental exports.

Acceptance criteria (restated)
- NDJSON writer:
  - one JSON object per line
  - stable key ordering / serialization
  - newline-terminated output
- Incremental integration:
  - use anchor store + anchored query wrapper to simulate incremental runs
- Unit tests:
  - deterministic output across reruns
  - no-op when unchanged (no new lines appended; output bytes unchanged)
- CI green required before closing (macOS Xcode job uploads `ios-xcresult`).

Design choices
- NDJSON serialization uses `JSONSerialization` with `.sortedKeys` to enforce stable key ordering.
- Exporter uses persisted anchors to ensure append-safe behavior (no duplicate re-emission when unchanged).
- Record identity uses a deterministic `record_key` derived from stable sample fields in tests (type identifier + timestamps + value/unit for synthetic samples).

Plan
1) Add `ios/HealthDelta/Sources/NDJSONWriter.swift` with deterministic JSON serialization and newline termination.
2) Add `ios/HealthDelta/Sources/IncrementalNDJSONExporter.swift`:
   - loads anchor by key from `AnchorStore`
   - calls `AnchoredQuerying.execute`
   - appends deterministic NDJSON lines for returned samples
   - saves new anchor
3) Add `ios/HealthDelta/Tests/IncrementalNDJSONExporterTests.swift`:
   - first run writes expected NDJSON bytes
   - second run is a no-op (no file changes)
   - rerunning from a clean temp dir produces identical output bytes
4) Record audit artifacts (session log, review, TIME.csv) and close with CI proof.

Constraints
- Synthetic-only test data; no real HealthKit samples committed.
- No logging of sample values or identifiers.
- Repo mutations on Ubuntu host `GORF` only; Xcode runs only via GitHub Actions runner.
