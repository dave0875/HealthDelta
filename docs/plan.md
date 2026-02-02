# HealthDelta — Living Plan / Backlog

This document is a share-safe, living summary of where HealthDelta is and what to do next.

GitHub Issues remain the system of record for *why* work is done.

## Current state (high level)

End-to-end CLI pipeline exists (synthetic-test proven):
- ingest staging (`healthdelta ingest`)
- identity bootstrap (`healthdelta identity build`)
- de-identification (`healthdelta deid`)
- pipeline orchestration (`healthdelta pipeline run`)
- operator orchestration (`healthdelta run all`) with deterministic no-op behavior
- canonical NDJSON export (`healthdelta export ndjson`)
- DuckDB build/query (`healthdelta duckdb build|query`)
- share-safe reporting (`healthdelta report build|show`)
- Doctor’s Note (`healthdelta note build`) and operator integration
- export profiling (`healthdelta export profile`) for unpacked export directories

CI proof is mandatory:
- Linux job runs headless tests
- macOS self-hosted runner runs Xcode tests and uploads `ios-xcresult`

## Milestones

1) Robust export handling at scale
   - canonical export layout detection
   - staging of only the intended asset set (avoid slow broad scans)
2) Strong identity safety + human review UI
   - unverified link review and confirmation workflow
3) Incremental HealthKit continuation (anchors)
   - anchored queries, persistence, and safe replay
4) Production-grade share-safe collaboration
   - packaging/share bundles and validation tooling
5) Hospital record coverage (Epic/MyChart via Apple Health clinical records)
   - expand FHIR/CDA coverage and subject resolution
   - share-safe provenance and evidence bundles
   - CI-enforced governance guardrails

## Next issues (priority order)

These issues are intended as small vertical slices.

Completed
- Issues #1-#86 are closed (bootstrap through governance/evidence guardrails for FHIR, NDJSON, reporting, and CI policy enforcement).
- Issue #117 is closed (managed hidden worktree root + auto-prune + CI path guardrail).

Active governance carryover
1) Issue #72 - Governance: plan refresh + CI issue reference gate (active)
   - https://github.com/dave0875/HealthDelta/issues/72
2) Issue #92 - Governance: CI guardrails for issue discipline (active)
   - https://github.com/dave0875/HealthDelta/issues/92

New planning phase: Orin production deployment target (`orin.local`)
3) Issue #120 - Planning: Orin production deployment MMF backlog
   - https://github.com/dave0875/HealthDelta/issues/120
4) Issue #121 - Orin MMF: export inventory + PHI field map (closed)
   - https://github.com/dave0875/HealthDelta/issues/121
5) Issue #122 - Orin MMF: local model/runtime matrix for summaries + risk flags (closed)
   - https://github.com/dave0875/HealthDelta/issues/122
6) Issue #123 - Orin MMF: ingest-to-summary vertical slice on backend (closed)
   - https://github.com/dave0875/HealthDelta/issues/123
7) Issue #124 - Orin MMF: risk flags v1 with evidence + disclaimers (closed)
   - https://github.com/dave0875/HealthDelta/issues/124
8) Issue #125 - Orin MMF: trend analysis v1 for longitudinal records (closed)
   - https://github.com/dave0875/HealthDelta/issues/125
9) Issue #126 - Orin MMF: grounded Q&A v1 with abstain behavior (closed)
   - https://github.com/dave0875/HealthDelta/issues/126
10) Issue #127 - Orin MMF: production deployment + rollback proof on orin.local (closed)
    - https://github.com/dave0875/HealthDelta/issues/127
11) Issue #128 - Orin MMF: CI safety guardrails for PHI leakage + disclosure requirements (closed)
    - https://github.com/dave0875/HealthDelta/issues/128

## Operating rules (quick reference)

- No repo mutations without a GitHub issue capturing WHY.
- Synthetic-only test fixtures; never commit real exports.
- Never log PII/PHI or absolute paths that may contain names.
- `.ai/` prompts/sessions/reviews + `.ai/time/time.csv` are required for completion.
