# Session 2

Issue: #250

## Prompt
Add a bulk DuckDB canonical baseline loader and fix the timestamp contract so SQL and Python ingest paths store plain TIMESTAMP values consistently.

## Work
- Added canonical SQL timestamp normalization for bulk DuckDB loads.
- Changed Python timestamp parsing to insert naive UTC values into DuckDB TIMESTAMP columns.
- Forced the DuckDB regression test through a non-UTC timezone to catch local-time shifts.

## Verification
- `.venv/bin/python -m py_compile healthdelta/duckdb_tools.py tests/test_duckdb.py healthdelta/ndjson_export.py tests/test_ndjson_export.py`
- `.venv/bin/python -m unittest tests.test_duckdb -v` skipped locally because this `.venv` lacks duckdb
- `.venv/bin/python -m unittest tests.test_ndjson_export.TestNdjsonExport.test_export_ndjson_normalizes_real_world_fhir_validation_edges -v`
- `git diff --check`
