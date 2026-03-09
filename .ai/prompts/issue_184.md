---
Story
As a clinical records operator,
I want FHIR Condition resources mapped into canonical NDJSON records,
So that condition data is queryable and auditable in the pipeline.

Context / Why
Conditions are foundational for clinical summaries. Current coverage is limited to baseline resources and lacks canonical Condition records.

Acceptance Criteria
- Given share-safe FHIR Condition fixtures, when the pipeline runs, then it emits canonical NDJSON condition records with deterministic `record_key` and `canonical_person_id` fields.
- Canonical condition records include: code system, code, display, clinical status, verification status, and onset date/time when present.
- Missing/invalid fields are handled with deterministic null/empty behavior and logged in a share-safe warning summary.
- Unit tests cover at least one complete Condition example and one missing-field example.
- CI proof: GitHub Actions `CI` workflow, job `Linux (non-iOS tests)`, passes with the new tests.

Out of Scope
- Mapping non-Condition FHIR resources.
- UI changes or report formatting beyond required warnings.

Notes
- Follow TDD for parsing/mapping logic.
- Update NDJSON validation rules if a new record type is introduced.
---
