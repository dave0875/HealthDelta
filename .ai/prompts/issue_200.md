---
Story
As a pipeline operator,
I want Organization resources mapped into canonical NDJSON,
So that clinical records can attribute facilities consistently.

Context / Why
Missing Organization mapping blocks attribution and coverage reporting.

Acceptance Criteria
- Given synthetic Organization fixtures, when the NDJSON export runs, then Organization entities are emitted with stable canonical ids and include name/type/address when present.
- Given Organization references from mapped resources, when the NDJSON export runs, then Organization ids resolve without unresolved reference warnings.
- Given Organization mapping tests, when CI runs, then CI job Linux (non-iOS tests) in .github/workflows/ci.yml passes.

Out of Scope
- UI review tools.
- Real patient exports or PHI/PII fixtures.

Notes
- Keep fixtures synthetic and share-safe.
---
