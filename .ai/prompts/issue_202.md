---
Story
As a pipeline operator,
I want Location resources mapped into canonical NDJSON,
So that clinical records can attribute care locations consistently.

Context / Why
Location references are common in encounters and observations but are not yet canonicalized.

Acceptance Criteria
- Given synthetic Location fixtures, when the NDJSON export runs, then Location entities are emitted with stable canonical ids and include name/address when present.
- Given Location references from mapped resources, when the NDJSON export runs, then Location ids resolve without unresolved reference warnings.
- Given Location mapping tests, when CI runs, then CI job Linux (non-iOS tests) in .github/workflows/ci.yml passes.

Out of Scope
- UI review tools.
- Real patient exports or PHI/PII fixtures.

Notes
- Keep fixtures synthetic and share-safe.
---
