Issue: https://github.com/dave0875/HealthDelta/issues/31

Scope / intent (immutable)
- Introduce a protocol-based abstraction for HealthKit anchored queries.
- Provide a fake implementation for deterministic unit tests without device/entitlements/data dependencies.

Acceptance criteria (restated)
- Protocol abstraction for anchored queries.
- Fake implementation for tests.
- Unit tests prove:
  - anchor progression behavior is deterministic
  - no-op when no new samples
- CI green required before closing (macOS Xcode job uploads `ios-xcresult`).

Design choices
- Protocol: `AnchoredQuerying` with a single async method returning `AnchoredQueryResult` (samples, deleted, newAnchor).
- Live implementation uses `HKAnchoredObjectQuery` bridged into Swift concurrency via `withCheckedThrowingContinuation`.
- Fake implementation is a deterministic, script-driven query client for unit tests.

Plan
1) Add `ios/HealthDelta/Sources/AnchoredQueryClient.swift`:
   - `AnchoredQueryResult`
   - `AnchoredQuerying` protocol
   - `HealthKitAnchoredQueryClient` (live; not exercised in tests)
   - `FakeAnchoredQueryClient` (tests)
2) Add `ios/HealthDelta/Tests/AnchoredQueryClientTests.swift` verifying anchor progression and no-op behavior.
3) Record audit artifacts (session log, review, TIME.csv) and close with CI proof.

Constraints
- Never log sample values or identifiers.
- Repo mutations on Ubuntu host `GORF` only; Xcode runs only via GitHub Actions runner.
