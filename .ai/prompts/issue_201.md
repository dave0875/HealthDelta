---
Story
As a pipeline operator,
I want Practitioner resources mapped into canonical NDJSON,
So that clinical records can attribute providers consistently.

Context / Why
Provider attribution depends on Practitioner resources that are not yet canonicalized.

Acceptance Criteria
- Given synthetic Practitioner fixtures, when the NDJSON export runs, then Practitioner entities are emitted with stable canonical ids and include name/identifier when present.
- Given Practitioner references from mapped resources, when the NDJSON export runs, then Practitioner ids resolve without unresolved reference warnings.
- Given Practitioner mapping tests, when CI runs, then CI job Linux (non-iOS tests) in .github/workflows/ci.yml passes.

Out of Scope
- UI review tools.
- Real patient exports or PHI/PII fixtures.

Notes
- Keep fixtures synthetic and share-safe.
---
