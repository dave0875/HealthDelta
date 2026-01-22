# ISSUE-0036: iOS: export manifest.json for NDJSON outputs (deterministic)

GitHub: https://github.com/dave0875/HealthDelta/issues/36

## Objective
Produce a deterministic iOS export manifest so NDJSON output integrity and row counts can be validated without scanning NDJSON payloads.

## Context / Why
The Python pipeline uses manifests for determinism and auditability. iOS exports need equivalent lightweight metadata so transferred artifacts can be verified consistently.

## Acceptance Criteria
- Given an iOS run directory with NDJSON outputs, when writing `manifest.json`, then it contains `run_id`, file hashes/sizes, and row counts per stream.
- Given identical NDJSON outputs, when generating the manifest twice, then `manifest.json` bytes are identical.

## Non-Goals
- Compression/chunking.
- Multi-stream manifest completeness beyond the current iOS skeleton.

## Risks
- Risk: JSON serialization could be non-deterministic.
  - Mitigation: Use `JSONSerialization` with `.sortedKeys` and stable sorting of arrays.

## Test Plan
- iOS unit tests via CI (macOS runner with `ios-xcresult` artifact).
- Linux: `python3 -m unittest discover -s tests -p 'test_*.py'` (should remain green).

## Rollback Plan
- Revert commits; iOS exports continue without a manifest.

