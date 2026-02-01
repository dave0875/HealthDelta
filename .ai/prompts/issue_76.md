---
Story
As an operator,
I want MedicationStatement and MedicationDispense resources exported,
So that inpatient and discharge meds are visible.

Context / Why
Current export focuses on MedicationRequest; statements/dispenses are common in patient portals.

Acceptance Criteria
- NDJSON includes MedicationStatement/MedicationDispense rows with event_time from effective[x] or whenHandedOver.
- DuckDB supports these in medication tables or a new table with report coverage.
- Tests cover each resource type.

Out of Scope
- Medication code normalization.
---
