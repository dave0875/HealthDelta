# ISSUE-0042: ADR: ingestion paths convergence (export.zip vs iOS incremental)

GitHub: https://github.com/dave0875/HealthDelta/issues/42

## Objective
Add an ADR that documents the dual ingestion paths and their shared invariants so future work converges rather than drifts.

## Context / Why
HealthDelta now supports an iOS incremental export path in addition to the Apple Health export directory / export.zip pipeline. Without an explicit ADR, future schema and pipeline work risks inconsistencies, privacy regressions, and non-deterministic behavior.

## Acceptance Criteria
- Given both ingestion paths, when reading the ADR, then a maintainer can clearly identify:
  - how each path produces artifacts and where they live
  - which invariants are non-negotiable (determinism, no PII, person-keying)
  - how canonical NDJSON schema aligns (current and planned)
- `AGENTS.md` references the ADR.
- CI is green before closing.

## Non-Goals
- Implementing full schema convergence or adding new ingestion code.

## Risks
- Risk: ADR becomes stale as new streams are added.
  - Mitigation: Document invariants and field-level contracts; keep path diagrams high-level.

## Test Plan
- Local: `python3 -m unittest discover -s tests -p 'test_*.py' -v`
- CI: green run link + macOS `ios-xcresult` artifact

## Rollback Plan
- Revert ADR/doc references; no runtime behavior impacted.
