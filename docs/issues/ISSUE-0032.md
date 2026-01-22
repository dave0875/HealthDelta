# Issue 32 — iOS: incremental export skeleton (NDJSON writer) using anchors

GitHub: https://github.com/dave0875/HealthDelta/issues/32

## Objective
Create a thin, testable incremental export skeleton on iOS that writes deterministic NDJSON from anchored query results and uses persisted anchors to avoid duplicates.

## Context
The project requires incremental continuation via HealthKit anchored queries. This slice proves the flow and determinism without relying on `export.zip`.

## Acceptance Criteria (from GitHub issue)
- NDJSON writer component that writes one JSON object per line with stable serialization and newline termination.
- Integrate with anchor store + query wrapper to simulate incremental runs.
- Unit tests prove deterministic output across reruns and no-op when unchanged.
- CI green required before closing (macOS Xcode job with `ios-xcresult`).

## Non-goals
- Full HealthKit coverage or schema.
- Clinical records.
- UI.

## Risks
- Deterministic serialization in Swift requires care; mitigate with `.sortedKeys` and fixed formatting.
- Anchors must be persisted correctly to guarantee append-safe behavior.

## Test Plan
- Scripted fake anchored query returns:
  - first run: 1 synthetic sample + new anchor
  - second run: 0 samples + same anchor
- Assert:
  - first run produces NDJSON bytes
  - second run does not mutate output file
  - repeated clean runs produce identical output bytes

## Rollback Plan
- Revert commits referencing Issue #32.

