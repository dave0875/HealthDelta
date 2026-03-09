---
Story
As a clinical records pipeline,
I want Observation resources (labs/vitals) mapped from hospital FHIR exports into canonical NDJSON,
So that clinical measurements can be analyzed consistently.

Context / Why
Observations are the backbone for labs and vitals. Without canonical Observation rows, reports and downstream analytics lack measurable signals.

Acceptance Criteria
- Given synthetic hospital FHIR Observation fixtures (including `code`, `valueQuantity`, and `component`), when running `healthdelta export ndjson`, then `observation.ndjson` includes deterministic rows with required keys (`record_id`, `record_type`, `source`, `source_file`, `observation_id`, `code`, `value`, `unit`, `effective_start`, `effective_end`, `subject_reference`) and no PHI/PII.
- Given Observation rows with `encounter` references, when building DuckDB, then `observations` can be joined to `encounters` by `encounter_id` when present.
- Given the report build, then coverage summaries include Observation counts by `source` and `code_system`.
- Tests cover Observation mapping (including components) and pass in workflow `CI`, job `Linux (non-iOS tests)` with artifact `linux-unittest`.

Out of Scope
- Interpretation or clinical decision logic.
- UI visualization changes.

Notes
- Preserve deterministic ordering and ensure component rows are stable across runs.
---
