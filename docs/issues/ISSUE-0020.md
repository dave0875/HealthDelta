# ISSUE-0020: NDJSON validation (schema checks + share-safe assertions)

GitHub: https://github.com/dave0875/HealthDelta/issues/20

## Objective
Provide a fast, deterministic validator for canonical NDJSON streams so downstream consumers can trust exports and catch share-safety regressions early.

## Context / Why
HealthDelta exports NDJSON from multiple sources and modes. A built-in validator creates a tight feedback loop, prevents accidental drift in required fields, and supports test-only banned-token checks to guard against PII leakage.

## Acceptance Criteria
- Add `healthdelta export validate --input <ndjson_dir>` that:
  - validates newline-delimited JSON objects
  - checks required keys per stream
  - supports banned token/pattern assertions (configurable for synthetic tests)
- Synthetic-only tests with both passing and failing cases.
- Short runbook documenting validator behavior.

## Non-Goals
- Full JSONSchema formalization.
- Validating source semantics (e.g., code systems) beyond required fields and share-safe checks.

## Risks
- Risk: overly strict rules could reject valid future exports.
  - Mitigation: start with a minimal baseline key set and make stricter rules opt-in later.

## Test Plan
- Local: `python3 -m unittest discover -s tests -p 'test_*.py'`
- CI: verify green run (Linux + macOS) with `ios-xcresult` artifact.

## Rollback Plan
- Revert Issue #20 commit(s) to remove the validator and CLI wiring.

