---
Story
As a pipeline operator,
I want Coverage (insurance) resources mapped into canonical NDJSON,
So that payer context is available in share-safe analytics.

Context / Why
Coverage data helps interpret clinical records and is present in many exports.
Without mapping, payer context is lost and reporting lacks insurance metadata.

Acceptance Criteria
- Given a synthetic clinical records fixture containing FHIR Coverage entries, when `healthdelta export ndjson` runs, then NDJSON `coverage` (or equivalent canonical) records are emitted with stable IDs, type, subscriber relationship, period, and subject references.
- Given Coverage entries with payor Organization references, when the export runs, then those references are preserved in NDJSON (IDs or canonical link fields).
- Given CI runs on the change branch, when the `CI / Linux (non-iOS tests)` job completes, then NDJSON validation smoke and unit tests pass and upload their artifacts.

Out of Scope
- Billing or claims processing logic.
- PII expansion beyond share-safe metadata.

Notes
- Use synthetic-only fixtures.
- Coordinate with Organization mapping if needed (may be handled in separate issue).
---
