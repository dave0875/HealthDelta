---
Story
As a maintainer,
I want a reference integrity report that flags unresolved references,
So that data quality issues are visible without breaking the pipeline.

Context / Why
Weak references reduce usability and trust.

Acceptance Criteria
- A report lists counts of unresolved references by type (Encounter.subject, Procedure.subject, etc.).
- The report is share-safe and deterministic.
- Tests cover a mixed resolved/unresolved fixture.

Out of Scope
- Automatic repair.
---
