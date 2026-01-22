# Issue 30 — iOS: anchor persistence store module (file-backed) + unit tests

GitHub: https://github.com/dave0875/HealthDelta/issues/30

## Objective
Add a deterministic, file-backed anchor store for HealthKit anchored query continuation, with unit tests proving correct roundtrip behavior and robust handling of missing/corrupt files.

## Context
Incremental HealthKit sync requires durable `HKQueryAnchor` persistence. This must exist as a tested component before implementing any real queries.

## Acceptance Criteria (from GitHub issue)
- Implement a Swift module that stores anchors by key to app sandbox, with deterministic serialization and minimal versioning/migration.
- Unit tests verify save/load roundtrip, stable bytes for same input, and graceful missing/corrupt handling.
- No PHI/PII logging.
- CI green required before closing (macOS Xcode job with `ios-xcresult`).

## Non-goals
- Performing actual HealthKit queries.
- UI integration.

## Risks
- `NSKeyedArchiver` payload stability may vary across OS versions; mitigate by keeping a stable outer envelope and testing on CI simulator.
- HealthKit linkage might require explicit framework configuration in Xcodegen.

## Test Plan
- Tests run on iOS simulator:
  - serialize the same `HKQueryAnchor(fromValue:)` twice and assert identical bytes.
  - save then load and assert loaded anchor re-serializes to the same bytes.
  - missing file returns `nil` and corrupt file returns `nil` (no crash).

## Rollback Plan
- Revert commits referencing Issue #30.
- Fall back to no anchor persistence (sync not safe across restarts).

