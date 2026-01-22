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

## Next issues (priority order)

These issues are intended as small vertical slices.

Completed
1) Issue #17 — Export layout resolver (completed)
   - https://github.com/dave0875/HealthDelta/issues/17
2) Issue #18 — Ingest staging alignment + stage `export_cda.xml` (completed)
   - https://github.com/dave0875/HealthDelta/issues/18
3) Issue #19 — Pipeline/operator: rely on ingest for CDA staging (completed)
   - https://github.com/dave0875/HealthDelta/issues/19
4) Issue #20 — NDJSON validation command (completed)
   - https://github.com/dave0875/HealthDelta/issues/20
5) Issue #21 — Share bundle packaging (completed)
   - https://github.com/dave0875/HealthDelta/issues/21
6) Issue #22 — Profile-to-pipeline recommendations in `profile.md` (completed)
   - https://github.com/dave0875/HealthDelta/issues/22

Next (priority order)
1) Issue #23 — Plan refresh: extend backlog beyond #22
   - https://github.com/dave0875/HealthDelta/issues/23
2) Issue #24 — Operator: persistent identity across runs (stable `canonical_person_id`)
   - https://github.com/dave0875/HealthDelta/issues/24
3) Issue #25 — NDJSON schema: add `schema_version` + stable `record_key` per row
   - https://github.com/dave0875/HealthDelta/issues/25
4) Issue #26 — DuckDB loader: append-safe ingestion using `record_key` (no duplicates)
   - https://github.com/dave0875/HealthDelta/issues/26
5) Issue #27 — Share bundle: add `share verify` (allowlist + hashes)
   - https://github.com/dave0875/HealthDelta/issues/27
6) Issue #28 — Identity model: introduce PersonLink registry + `verification_state`
   - https://github.com/dave0875/HealthDelta/issues/28
7) Issue #29 — Identity workflow: CLI review/confirm for unverified PersonLinks
   - https://github.com/dave0875/HealthDelta/issues/29
8) Issue #30 — iOS: anchor persistence store module (file-backed) + unit tests
   - https://github.com/dave0875/HealthDelta/issues/30
9) Issue #31 — iOS: HealthKit anchored query wrapper (mockable) + tests
   - https://github.com/dave0875/HealthDelta/issues/31
10) Issue #32 — iOS: incremental export skeleton (NDJSON writer) using anchors
   - https://github.com/dave0875/HealthDelta/issues/32

## Operating rules (quick reference)

- No repo mutations without a GitHub issue capturing WHY.
- Synthetic-only test fixtures; never commit real exports.
- Never log PII/PHI or absolute paths that may contain names.
- `.codex/` prompts/sessions/reviews + `TIME.csv` are required for completion.
