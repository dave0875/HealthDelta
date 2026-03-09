---
Story
As a clinical records operator,
I want FHIR Medication and Allergy resources mapped into canonical NDJSON records,
So that medication and allergy history can be audited and queried consistently.

Context / Why
Medication and allergy history are critical for downstream summaries and safety checks. We need canonical NDJSON records to support reporting and future review workflows.

Acceptance Criteria
- Given share-safe FHIR MedicationStatement/MedicationRequest fixtures, when the pipeline runs, then it emits canonical NDJSON medication records with deterministic `record_key` and `canonical_person_id` fields.
- Given share-safe FHIR AllergyIntolerance fixtures, when the pipeline runs, then it emits canonical NDJSON allergy records with deterministic `record_key` and `canonical_person_id` fields.
- Canonical records include code system, code, display, status, and authored/onset time when present.
- Unit tests cover at least one complete medication example, one complete allergy example, and one missing-field example for each.
- CI proof: GitHub Actions `CI` workflow, job `Linux (non-iOS tests)`, passes with the new tests.

Out of Scope
- Mapping immunizations, procedures, or diagnostic reports.
- UI changes or new operator screens.

Notes
- Follow TDD for parsing/mapping logic.
- Update NDJSON validation rules if new record types are introduced.
---
