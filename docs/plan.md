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
- Issues #1–#69 (bootstrap through CLI progress + CD, including iOS incremental export pipeline) are closed.
- Issues #33–#42 (plan refresh, iOS deterministic exports, staging, DuckDB/reporting, and ADR convergence) are closed.

Next (priority order)
1) Issue #72 — Governance: plan refresh + CI issue reference gate (in progress)
   - https://github.com/dave0875/HealthDelta/issues/72
2) Issue #73 — FHIR export: Encounter
   - https://github.com/dave0875/HealthDelta/issues/73
3) Issue #74 — FHIR export: Procedure
   - https://github.com/dave0875/HealthDelta/issues/74
4) Issue #75 — FHIR export: DiagnosticReport (+ Observation linkage)
   - https://github.com/dave0875/HealthDelta/issues/75
5) Issue #76 — FHIR export: MedicationStatement + MedicationDispense
   - https://github.com/dave0875/HealthDelta/issues/76
6) Issue #77 — FHIR export: AllergyIntolerance + Immunization
   - https://github.com/dave0875/HealthDelta/issues/77
7) Issue #78 — Identity: subject.identifier resolution
   - https://github.com/dave0875/HealthDelta/issues/78
8) Issue #79 — Reporting: unresolved reference integrity report
   - https://github.com/dave0875/HealthDelta/issues/79
9) Issue #80 — De-id: scrub FHIR free-text/narrative
   - https://github.com/dave0875/HealthDelta/issues/80
10) Issue #81 — CDA export: discharge summary coverage
   - https://github.com/dave0875/HealthDelta/issues/81
11) Issue #82 — NDJSON: JSON schema + CI validation
   - https://github.com/dave0875/HealthDelta/issues/82
12) Issue #83 — DuckDB/reporting: include new FHIR types
   - https://github.com/dave0875/HealthDelta/issues/83
13) Issue #84 — Provenance: share-safe source_system tagging
   - https://github.com/dave0875/HealthDelta/issues/84
14) Issue #85 — Share bundle: hospital record evidence pack
   - https://github.com/dave0875/HealthDelta/issues/85
15) Issue #86 — CI: enforce audit logs + evidence artifacts
   - https://github.com/dave0875/HealthDelta/issues/86

## Operating rules (quick reference)

- No repo mutations without a GitHub issue capturing WHY.
- Synthetic-only test fixtures; never commit real exports.
- Never log PII/PHI or absolute paths that may contain names.
- `.ai/` prompts/sessions/reviews + `.ai/time/time.csv` are required for completion.
