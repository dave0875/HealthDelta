---
Story
As an operator,
I want CDA parsing to cover discharge summary headers and key sections,
So that hospital documents add structured timeline context.

Context / Why
CDA often includes discharge summaries and problems not in FHIR JSON.

Acceptance Criteria
- CDA parsing includes additional observation-like and encounter-like entries (share-safe).
- NDJSON export remains deterministic and validated.
- Tests cover at least two new CDA sections.

Out of Scope
- Full CDA narrative text extraction.
---
