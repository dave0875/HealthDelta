---
Story
As a pipeline operator,
I want Provenance resources mapped into canonical NDJSON,
So that clinical records include share-safe attribution and audit context.

Context / Why
Provenance is required for evidence bundles and audit trails but is not yet canonicalized.

Acceptance Criteria
- Given synthetic Provenance fixtures, when the NDJSON export runs, then Provenance entities are emitted with stable canonical ids and include recorded/agent/target fields when present.
- Given Provenance references from mapped resources, when the NDJSON export runs, then Provenance ids resolve without unresolved reference warnings.
- Given Provenance mapping tests, when CI runs, then CI job Linux (non-iOS tests) in .github/workflows/ci.yml passes.

Out of Scope
- UI review tools.
- Real patient exports or PHI/PII fixtures.

Notes
- Keep fixtures synthetic and share-safe.
---
