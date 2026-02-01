---
Story
As a maintainer,
I want a formal JSON schema for NDJSON records with versioning,
So that compatibility and validation are enforced in CI.

Context / Why
New resource coverage increases schema complexity.

Acceptance Criteria
- A JSON schema exists for each NDJSON stream, versioned and validated in CI.
- ndjson validate enforces schema version compatibility.
- Tests cover invalid schema detection.

Out of Scope
- Backward conversion tools.
---
