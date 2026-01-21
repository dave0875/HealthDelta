# ISSUE-0017: Export layout resolver (canonical export root detection)

GitHub: https://github.com/dave0875/HealthDelta/issues/17

## Objective
Provide a deterministic, share-safe resolver for unpacked Apple Health export directory layouts so that multiple commands can agree on canonical paths without broad scans.

## Context / Why
Unpacked exports may be rooted directly or nested under `apple_health_export/`. A shared resolver reduces performance risk on large trees and prevents accidental inclusion of unrelated files.

## Acceptance Criteria
- Add a shared, testable resolver that returns paths (relative to export root) for:
  - export.xml (required)
  - export_cda.xml (optional)
  - clinical JSON directory (optional; prefer clinical-records/)
- Resolver is deterministic and share-safe (no absolute paths in outputs/logs).
- Update `healthdelta export profile` to use the resolver.
- Add unit tests with synthetic directory variants.

## Non-Goals
- No changes to staging/run_id derivation (Issue #18).
- No changes to pipeline/operator CDA staging behavior (Issue #19).

## Risks
- Risk: layout resolver misses an edge-case variant.
  - Mitigation: keep candidates explicit and add fixtures for known variants; extend via new issues if needed.

## Test Plan
- Local: `python3 -m unittest discover -s tests`
- CI: verify green run (Linux + macOS) with `ios-xcresult` artifact.

## Rollback Plan
- Revert resolver module + profile integration; profile returns to scanning the provided input directory directly.

