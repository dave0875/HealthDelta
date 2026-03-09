---
Story
As a compliance-minded operator,
I want NDJSON validation rules for clinical records mappings,
So that mapping outputs are consistently checked for required fields.

Context / Why
Clinical records mappings introduce new resource types that need explicit validation to prevent regressions.

Acceptance Criteria
- Given clinical records NDJSON outputs, when `healthdelta ndjson validate` runs, then required-field checks exist for the clinical record resource types covered by the mapping batch (e.g., Condition, Medication/Allergy, Immunization/Procedure, Encounter, Observation).
- Given the validation changes, when tests run, then `tests/test_ndjson_validate.py` covers at least one new clinical records validation rule.
- Given the updates, when CI runs, then workflow `CI` job `Linux (non-iOS tests)` passes.

Out of Scope
- Implementing the mapping logic for clinical resources.
- Adding non-synthetic test data.

Notes
Validation failures must be deterministic and share-safe.
---
