# ADR_2 — Ingest `run_id` Derivation for Deterministic Staging

Issue: https://github.com/dave0875/HealthDelta/issues/4
Date: 2026-01-20

## Context
Bootstrap ingest must create stable, testable staging artifacts. We need a `run_id` that is deterministic/reproducible so that identical inputs map to the same run directory and downstream artifacts can be cached and compared.

## Decision
Derive `run_id` from input content:
- For zip inputs: `run_id = sha256(export.zip bytes)`
- For unpacked directory inputs: `run_id = sha256(relpath + sha256(file bytes))` over:
  - `export.xml`
  - all discovered `*.json` files
  sorted by relative path within the input directory

## Alternatives Considered
- Random UUID per run: avoids collisions but breaks reproducibility and makes test fixtures harder to compare.
- Timestamp-based ID: human-friendly but not deterministic.
- Hash of staged output directory: circular dependency and sensitive to staging format changes.

## Consequences
- Re-running ingest on the same input content produces the same `run_id` and targets the same staging directory.
- Manifest time fields remain non-deterministic by design and are isolated under `timestamps.*`.
- Future changes to which files are included in the digest must be made via a GitHub issue + ADR update, as it impacts reproducibility.

