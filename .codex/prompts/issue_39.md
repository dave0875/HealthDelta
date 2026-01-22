Issue: https://github.com/dave0875/HealthDelta/issues/39

Scope / intent (immutable)
- Update reporting outputs to surface iOS-exported data distinctly so operators can validate incremental export coverage and timelines.

Acceptance criteria (restated)
- Update report build outputs to include iOS source rows where present.
- Add synthetic tests proving deterministic outputs.
- Record audit artifacts (prompt/session/review/TIME.csv) and close with green CI.

Design notes
- The DB `source` column remains `healthkit|fhir|cda` for canonical pipeline inputs.
- For iOS-ingested rows, the DuckDB loader sets `source_file` to `ndjson/...` (relative to the iOS export root).
- Reporting will treat rows with `source_file LIKE 'ndjson/%'` as `source='ios'` for coverage and timeline breakdowns (reporting-only derived label).

Plan
1) Update `healthdelta/reporting.py` aggregation queries:
   - coverage-by-source and timeline queries use `CASE WHEN source_file LIKE 'ndjson/%' THEN 'ios' ELSE source END`.
2) Add synthetic tests:
   - build a DB from an iOS export dir (via `healthdelta duckdb build`)
   - run `healthdelta report build`
   - assert `coverage_by_source.csv` and `timeline_daily_counts.csv` include `source=ios` rows deterministically.
3) Record audit artifacts and close with CI proof.

Constraints
- Repo mutations on Ubuntu host `GORF` only.
- Synthetic-only tests/fixtures.

