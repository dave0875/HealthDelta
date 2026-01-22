# Issue 31 — iOS: HealthKit anchored query wrapper (mockable) + tests

GitHub: https://github.com/dave0875/HealthDelta/issues/31

## Objective
Create a mockable, protocol-based anchored query wrapper so incremental sync logic can be tested deterministically without real HealthKit data or device dependencies.

## Context
HealthKit anchored queries require stateful anchors and are hard to test directly. A clean abstraction enables unit tests and safer incremental export development.

## Acceptance Criteria (from GitHub issue)
- Introduce a protocol-based abstraction for anchored queries.
- Provide a fake implementation for tests.
- Unit tests prove deterministic anchor progression and no-op behavior on no new samples.
- CI green required before closing (macOS Xcode job with `ios-xcresult`).

## Non-goals
- Full exporter/NDJSON writing.
- Real device integration or entitlements validation beyond simulator compilation/tests.

## Risks
- Bridging `HKAnchoredObjectQuery` to async/await must be correct to avoid leaks or double-callbacks.
- Fake should avoid leaking sample values and be deterministic by construction.

## Test Plan
- Scripted fake query client returning:
  - first page: 1 sample + new anchor
  - second page: 0 samples + same anchor
- Assert wrapper returns deterministic anchor progression and that “no new samples” is a no-op.

## Rollback Plan
- Revert commits referencing Issue #31.

