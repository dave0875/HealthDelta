# ADR 4: Ingestion paths convergence (Apple export directory/zip vs iOS incremental)

Status: Accepted

## Context
HealthDelta currently has two ingestion paths that can produce analyzable artifacts:

1) **Apple Health export** (bootstrap-style):
   - Input: `export.zip` or an unpacked export directory containing `export.xml` and optional clinical assets.
   - Output: staged run directory + derived artifacts (identity, de-id, canonical NDJSON, DuckDB, reports).

2) **iOS incremental export** (continuation-style):
   - Input: iOS app-managed HealthKit anchored queries.
   - Output: iOS-written NDJSON + deterministic manifest (and anchors on-device) that can be ingested into the Python toolchain and loaded into DuckDB.

Both paths must remain share-safe and deterministic. Without an explicit convergence narrative, it is easy for schemas, invariants, and privacy guarantees to drift.

## Decision
We treat the Apple export pipeline and the iOS incremental export as two *front ends* that converge on shared, stable contracts:

### 1) Shared invariants (non-negotiable)
- **No PII/PHI in derived artifacts**: canonical NDJSON streams, DuckDB databases, reports, and “doctor note” outputs must not contain names, DOBs, identifiers, addresses, or free-text clinical narratives.
- **Determinism**: same input bytes and same configuration produce byte-stable outputs where feasible; ordering is explicit; JSON serialization is stable.
- **Person-keying**: downstream artifacts are keyed by `canonical_person_id` (non-PII UUID) and never by raw patient identifiers or names.
- **Artifact-based verification**: correctness is proven through CI logs and uploaded artifacts, not informal local claims.

### 2) Path A: Apple export directory/zip → canonical artifacts
Canonical flow:
- `healthdelta ingest ...` → `data/staging/<run_id>/` (manifest/layout; copies/references raw input)
- `healthdelta identity build ...` → `data/identity/...` (canonical people/aliases)
- `healthdelta deid ...` (share mode) → `data/deid/<run_id>/` (share-safe copies + mapping)
- `healthdelta export ndjson ...` → canonical NDJSON streams
- `healthdelta duckdb build ...` → deterministic DuckDB tables
- `healthdelta report build ...` / `healthdelta note build ...` → share-safe summaries

### 3) Path B: iOS incremental export → canonical artifacts
Canonical flow:
- iOS app exports a deterministic run directory containing:
  - `manifest.json` (sha256, sizes, row counts; no timestamps)
  - `ndjson/observations.ndjson` (one row per event; newline-terminated; deterministic ordering)
- Python toolchain convergence options:
  - Direct: `healthdelta duckdb build --input <ios_run_dir> ...` (loader recognizes iOS layout)
  - Optional: `healthdelta ingest ios --input <ios_run_dir> ...` to produce a staging run directory (for consistent operator workflows)
- Reporting remains based on DuckDB + report/note commands.

### 4) NDJSON schema alignment (current + planned)
Current alignment relies on a stable set of **required fields** and a controlled mapping layer:
- Required across streams/paths:
  - `canonical_person_id`
  - `event_time` (best-available timestamp for ordering/coverage)
  - `run_id`
  - `source` (high-level provenance)
  - `source_file` (relative/redacted path)
- iOS incremental observation NDJSON includes iOS-specific fields (e.g., `sample_type`, `start_time`).
  - DuckDB loading maps these into the canonical table shape (e.g., `sample_type` → `hk_type`, `start_time` → `event_time`) to keep downstream queries stable.

Planned evolution:
- Expand canonical NDJSON streams beyond observations (documents/meds/conditions) in a way that preserves the required-field contract.
- Keep per-source/per-path extensions additive and explicitly mapped into DuckDB schema rather than creating parallel, divergent tables.

## Consequences
- Maintainers can add ingestion capabilities (new HealthKit types, more FHIR/CDA extraction, richer iOS streams) while preserving stable downstream contracts.
- Operators can select the appropriate entrypoint (export directory profile, pipeline run, iOS export ingestion) without changing analysis workflows.
- Convergence work becomes explicit (new mappings documented; schema additions are deliberate), reducing the risk of privacy or determinism regressions.

## Cross-references
- Issue #4: ingest staging (Apple export directory/zip)
- Issue #7: pipeline orchestration
- Issue #8: canonical NDJSON export
- Issue #9: DuckDB build/query
- Issue #10: reports
- Issue #36–#40: iOS incremental export + ingestion + analysis plumbing
- Issue #42: this ADR
