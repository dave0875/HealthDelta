# ISSUE-0035: iOS: deterministic export directory layout for NDJSON outputs

GitHub: https://github.com/dave0875/HealthDelta/issues/35

## Objective
Provide a stable, deterministic iOS on-disk layout for NDJSON exports so operators can locate and share outputs reliably.

## Context / Why
Issue #32 proves determinism in tests, but operator usage needs a stable directory structure under the app sandbox (rather than ad-hoc temp paths).

## Acceptance Criteria
- Given a fixed `run_id`, when deriving output paths, then the exporter uses deterministic paths under the app sandbox.
- Given repeated exporter runs with no changes, when re-running, then output bytes are unchanged.
- Given a first-time export, when writing output, then parent directories are created and file creation is best-effort atomic.

## Non-Goals
- Share sheet / UI.

## Risks
- Risk: “Atomic” appends are hard for large NDJSON files.
  - Mitigation: Use atomic creation for first write and append-only thereafter; keep no-op behavior to avoid unnecessary mutation.

## Test Plan
- iOS unit tests via CI (macOS runner with `ios-xcresult` artifact).
- Linux: `python3 -m unittest discover -s tests -p 'test_*.py'` (should remain green).

## Rollback Plan
- Revert commits; iOS exporter continues to accept caller-provided output paths.

