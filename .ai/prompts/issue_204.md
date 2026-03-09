---
Story
As a pipeline operator,
I want Binary resources and embedded attachments handled in canonical NDJSON,
So that evidence artifacts remain share-safe and traceable.

Context / Why
Attachments appear in DocumentReference and DiagnosticReport but lack share-safe handling guidance.

Acceptance Criteria
- Given synthetic Binary and attachment fixtures, when the NDJSON export runs, then Binary/attachment metadata is emitted with stable canonical ids and content is redacted or excluded for share-safe outputs.
- Given attachment references from mapped resources, when the NDJSON export runs, then attachment ids resolve without unresolved reference warnings.
- Given Binary/attachment mapping tests, when CI runs, then CI job Linux (non-iOS tests) in .github/workflows/ci.yml passes.

Out of Scope
- Storing raw binary payloads in share-safe bundles.
- Real patient exports or PHI/PII fixtures.

Notes
- Keep fixtures synthetic and share-safe.
---
