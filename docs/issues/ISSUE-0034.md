# ISSUE-0034: iOS: persistent single-user canonical_person_id (UUIDv4) for exports

GitHub: https://github.com/dave0875/HealthDelta/issues/34

## Objective
Add a persisted, non-PII-derived canonical person identifier to iOS NDJSON exports so downstream consumers can safely person-key streams.

## Context / Why
The iOS incremental exporter currently emits sample-derived rows without a person identifier. The system forbids deriving IDs from PII or device identifiers, but downstream tooling expects person-keyed NDJSON.

## Acceptance Criteria
- Given an iOS install on a single-user device, when exporting NDJSON, then every row includes a stable `canonical_person_id` UUID string.
- Given the app restarts, when loading the canonical person ID store, then the same UUID is returned.
- Given the exporter emits NDJSON, when parsing each line, then `canonical_person_id` exists on every row.

## Non-Goals
- Multi-person workflows on one device.
- Identity resolution beyond a single persisted ID.

## Risks
- Risk: Random ID generation breaks deterministic tests.
  - Mitigation: Inject a fixed ID provider for unit tests; store is file-backed for production.

## Test Plan
- iOS unit tests via CI (macOS runner with `ios-xcresult` artifact).
- Linux: `python3 -m unittest discover -s tests -p 'test_*.py'` (should remain green).

## Rollback Plan
- Revert commits and re-run CI; iOS exporter will revert to previous schema without `canonical_person_id`.

