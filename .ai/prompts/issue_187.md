---
Story
As a clinical records pipeline,
I want Encounter resources mapped from hospital FHIR exports into canonical NDJSON,
So that encounter-level context is queryable and reportable.

Context / Why
Clinical record exports include encounters that anchor observations, procedures, and document bundles. Without explicit Encounter mapping, downstream coverage and linkage metrics are incomplete.

Acceptance Criteria
- Given a synthetic hospital FHIR export containing Encounter resources, when running `healthdelta export ndjson`, then `encounter.ndjson` includes deterministic rows with required keys (`record_id`, `record_type`, `source`, `source_file`, `encounter_id`, `subject_reference`, `period_start`, `period_end`) and no PHI/PII.
- Given the new Encounter NDJSON rows, when running `healthdelta duckdb build`, then the `encounters` table includes the new rows and is joinable by `encounter_id`.
- Given the DuckDB build, when running `healthdelta report build`, then coverage reports include Encounter counts by `source`.
- Tests cover Encounter mapping and pass in workflow `CI`, job `Linux (non-iOS tests)` with artifact `linux-unittest`.

Out of Scope
- UI changes or visualization of encounters.
- Non-hospital export sources.

Notes
- Ensure deterministic ordering and stable `record_key` generation for Encounter rows.
---
