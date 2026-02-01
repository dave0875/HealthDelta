---
Story
As an operator,
I want AllergyIntolerance and Immunization exported,
So that allergy and vaccine history appears in canonical outputs.

Context / Why
These are common in Epic/MyChart clinical records and currently not exported.

Acceptance Criteria
- NDJSON includes AllergyIntolerance and Immunization rows with deterministic event_time selection.
- DuckDB load and report outputs include row coverage without regressions.
- Tests cover both resource types.

Out of Scope
- Terminology normalization.
---
