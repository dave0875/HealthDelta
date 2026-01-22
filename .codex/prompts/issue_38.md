Issue: https://github.com/dave0875/HealthDelta/issues/38

Scope / intent (immutable)
- Extend `healthdelta duckdb build` to ingest iOS-exported NDJSON artifacts (subset mapping) so iOS incremental exports can be queried via existing DuckDB/report tooling.

Acceptance criteria (restated)
- Extend `healthdelta duckdb build` to accept iOS export NDJSON inputs (documented mapping).
- Add synthetic tests proving load and stable query outputs.
- Record audit artifacts (prompt/session/review/TIME.csv) and close with green CI.

Design notes
- Input detection (iOS export root):
  - if `--input` contains `manifest.json` and `ndjson/observations.ndjson`, treat it as an iOS export/staging run directory and use `ndjson/` as the NDJSON root.
- Subset mapping (iOS → DuckDB observations table):
  - `canonical_person_id` → `canonical_person_id`
  - `source` → `source`
  - `sample_type` → `hk_type`
  - `start_time` → `event_time` (UTC normalized to seconds where applicable)
  - `record_key` → `record_key` (dedupe key)
  - `value_num`/`unit` → `value_num`/`unit`
  - `run_id`: taken from iOS `manifest.json` `run_id` (applied to all rows)
  - `source_file`: set to `ndjson/observations.ndjson` (relative to iOS export root)
- Documents/medications/conditions streams are optional for iOS input (tables remain created; missing files => zero rows).

Plan
1) Add an iOS input detection branch in `healthdelta/duckdb_tools.py`:
   - select NDJSON root and run_id
   - relax `documents.ndjson` requirement for iOS inputs
   - map iOS fields into the existing observations schema
2) Add synthetic tests loading an iOS export directory and asserting:
   - DB builds successfully
   - observations row count matches expected
   - rerun is append-safe (no duplicates)
3) Document the subset mapping in `docs/runbook_duckdb.md`.
4) Add required audit artifacts and close with CI proof.

Constraints
- Repo mutations on Ubuntu host `GORF` only.
- Synthetic-only fixtures/tests.

