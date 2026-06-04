Issue #250: Add bulk DuckDB load path for fresh canonical NDJSON baselines

Source of truth: GitHub Issue #250

Scope:
- Add DuckDB-side bulk projection for fresh canonical observations NDJSON imports.
- Preserve deterministic dedupe and existing append-safe behavior.
- Add focused regression coverage.

Non-goals:
- No schema changes.
- No report-content changes.
- No private data changes.
