Issue: https://github.com/dave0875/HealthDelta/issues/26

Scope / intent (immutable)
- Implement append-safe DuckDB ingestion using per-row `record_key` (Issue #25).
- Ensure rerunning `healthdelta duckdb build` against the same NDJSON input does not create duplicate rows.
- Keep loader streaming-safe and share-safe (no PII fields introduced; no network).

Acceptance criteria (restated)
- `healthdelta duckdb build` supports append-safe loading when DB exists (or explicitly requires `--replace`; choose one and document).
- Dedupe uses `record_key` per table deterministically.
- Synthetic tests prove: building twice does not increase row counts; canonical queries remain stable.
- Update `docs/runbook_duckdb.md` with schema + dedupe rules.
- CI green required before closing; produce audit artifacts (session log, review, TIME.csv).

Plan
1) Update `healthdelta/duckdb_tools.py`:
   - Add `record_key` column to each table (keep `event_key` for compatibility).
   - When `--replace` is set: recreate DB from scratch as today.
   - When DB exists and `--replace` is not set: create missing tables if needed and ingest NDJSON while skipping rows whose `record_key` already exists.
2) Update tests (`tests/test_duckdb.py`):
   - Include `record_key` in synthetic NDJSON fixtures.
   - Run `duckdb build` twice (2nd time without `--replace`) and assert row counts do not increase.
   - Assert query outputs remain share-safe (no synthetic PII strings).
3) Update docs (`docs/runbook_duckdb.md`):
   - Document `record_key` as the dedupe key and the new append-safe behavior.

Determinism rules
- Dedupe key is the NDJSON `record_key` string (required by validator as of schema_version=2).
- Ingestion order is deterministic (NDJSON file order); re-runs must be idempotent (no duplicates).
- Queries in tests use explicit ordering.

Privacy rules
- Loader only projects explicit, non-PII columns into tables.
- Tests use synthetic PII-like tokens and assert they never appear in outputs.

Execution constraints
- All repository mutations executed only on Ubuntu host `GORF`.
- GitHub interactions via `gh` CLI only.
