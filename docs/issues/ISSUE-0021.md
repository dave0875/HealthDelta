# ISSUE-0021: Share bundle packaging (share-safe archive)

GitHub: https://github.com/dave0875/HealthDelta/issues/21

## Objective
Provide a deterministic bundling command that packages only share-safe artifacts from a run so operators can move/collaborate without accidentally including staging/PII.

## Context / Why
Operators frequently need to transfer outputs between machines or to collaborators. A dedicated bundler reduces human error and enforces an explicit allowlist of share-safe artifacts.

## Acceptance Criteria
- Add `healthdelta share bundle --run <base_out>/<run_id> --out <path>.tar.gz`.
- Bundle includes only:
  - `deid/` (if present)
  - `ndjson/`
  - `duckdb/`
  - `reports/`
  - `note/`
  - run registry entry snippet (no PII)
- Deterministic archive ordering/metadata (as feasible).
- Synthetic tests verify staging is excluded and output is stable.

## Non-Goals
- Any network upload.
- Packaging raw staging/identity outputs.

## Risks
- Risk: archive metadata (timestamps/ownership) introduces non-determinism.
  - Mitigation: normalize tar metadata and gzip header timestamps.

## Test Plan
- Local: `python3 -m unittest discover -s tests -p 'test_*.py'`
- CI: verify green run (Linux + macOS) with `ios-xcresult` artifact.

## Rollback Plan
- Revert Issue #21 commit(s) to remove the bundler command and CLI wiring.

