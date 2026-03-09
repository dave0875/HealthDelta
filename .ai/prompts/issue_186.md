---
Story
As a clinical records operator,
I want FHIR Immunization and Procedure resources mapped into canonical NDJSON records,
So that immunization and procedure history can be audited and queried in the pipeline.

Context / Why
Immunization and procedure history are common in clinical exports and needed for longitudinal views. Canonical records are required for consistent reporting and future review workflows.

Acceptance Criteria
- Given share-safe FHIR Immunization fixtures, when the pipeline runs, then it emits canonical NDJSON immunization records with deterministic `record_key` and `canonical_person_id` fields.
- Given share-safe FHIR Procedure fixtures, when the pipeline runs, then it emits canonical NDJSON procedure records with deterministic `record_key` and `canonical_person_id` fields.
- Canonical records include code system, code, display, status, and occurrence time when present.
- Unit tests cover at least one complete immunization example, one complete procedure example, and one missing-field example for each.
- CI proof: GitHub Actions `CI` workflow, job `Linux (non-iOS tests)`, passes with the new tests.

Out of Scope
- Mapping medications, allergies, or conditions.
- UI changes or new operator screens.

Notes
- Follow TDD for parsing/mapping logic.
- Update NDJSON validation rules if new record types are introduced.
---
