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
7) Issue #23 — Plan refresh: extend backlog beyond #22 (completed)
   - https://github.com/dave0875/HealthDelta/issues/23
8) Issue #24 — Operator: persistent identity across runs (stable `canonical_person_id`) (completed)
   - https://github.com/dave0875/HealthDelta/issues/24
9) Issue #25 — NDJSON schema: add `schema_version` + stable `record_key` per row (completed)
   - https://github.com/dave0875/HealthDelta/issues/25
10) Issue #26 — DuckDB loader: append-safe ingestion using `record_key` (no duplicates) (completed)
   - https://github.com/dave0875/HealthDelta/issues/26
11) Issue #27 — Share bundle: add `share verify` (allowlist + hashes) (completed)
   - https://github.com/dave0875/HealthDelta/issues/27
12) Issue #28 — Identity model: introduce PersonLink registry + `verification_state` (completed)
   - https://github.com/dave0875/HealthDelta/issues/28
13) Issue #29 — Identity workflow: CLI review/confirm for unverified PersonLinks (completed)
   - https://github.com/dave0875/HealthDelta/issues/29
14) Issue #30 — iOS: anchor persistence store module (file-backed) + unit tests (completed)
   - https://github.com/dave0875/HealthDelta/issues/30
15) Issue #31 — iOS: HealthKit anchored query wrapper (mockable) + tests (completed)
   - https://github.com/dave0875/HealthDelta/issues/31
16) Issue #32 — iOS: incremental export skeleton (NDJSON writer) using anchors (completed)
   - https://github.com/dave0875/HealthDelta/issues/32

Next (priority order)
1) Issue #33 — Plan refresh: reflect #23–#32 completion and list #33–#42 (in progress)
   - https://github.com/dave0875/HealthDelta/issues/33
2) Issue #34 — iOS: persistent single-user `canonical_person_id` (UUIDv4) for exports
   - Add a per-device persisted UUIDv4 and include it on every iOS NDJSON row (no PII-derived IDs).
   - https://github.com/dave0875/HealthDelta/issues/34
3) Issue #35 — iOS: deterministic export directory layout for NDJSON outputs
   - Standardize app-sandbox output paths and ensure atomic, deterministic writes for a fixed `run_id`.
   - https://github.com/dave0875/HealthDelta/issues/35
4) Issue #36 — iOS: export `manifest.json` for NDJSON outputs (deterministic)
   - Emit a stable manifest (hashes/sizes/counts) so integrity can be validated without rescanning NDJSON payloads.
   - https://github.com/dave0875/HealthDelta/issues/36
5) Issue #37 — Python: ingest iOS NDJSON export directory into deterministic staging
   - Add a deterministic staging ingestion path for iOS NDJSON artifacts so they can flow into the Python toolchain.
   - https://github.com/dave0875/HealthDelta/issues/37
6) Issue #38 — DuckDB: load iOS NDJSON exports (subset mapping)
   - Extend the DuckDB loader to accept iOS-exported NDJSON streams via a documented subset schema mapping.
   - https://github.com/dave0875/HealthDelta/issues/38
7) Issue #39 — Reports: include iOS incremental export coverage in summaries
   - Ensure report outputs surface iOS-derived rows consistently so incremental exports can be validated for coverage.
   - https://github.com/dave0875/HealthDelta/issues/39
8) Issue #40 — Docs: runbook for iOS incremental exports and ingestion
   - Document iOS artifact locations and a safe transfer/ingest workflow into Python tooling.
   - https://github.com/dave0875/HealthDelta/issues/40
9) Issue #41 — CI: publish Linux unit test artifacts (and JUnit if feasible)
   - Improve CI evidence by persisting Linux test logs/results as artifacts with deterministic naming.
   - https://github.com/dave0875/HealthDelta/issues/41
10) Issue #42 — ADR: ingestion paths convergence (export.zip vs iOS incremental)
   - Record shared invariants and convergence plan so future schema/pipeline decisions remain consistent and auditable.
   - https://github.com/dave0875/HealthDelta/issues/42

## Operating rules (quick reference)

- No repo mutations without a GitHub issue capturing WHY.
- Synthetic-only test fixtures; never commit real exports.
- Never log PII/PHI or absolute paths that may contain names.
- `.codex/` prompts/sessions/reviews + `TIME.csv` are required for completion.
