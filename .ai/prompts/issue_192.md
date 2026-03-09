---
Story
As a pipeline operator,
I want ServiceRequest (referral/order) resources mapped into canonical NDJSON,
So that requested procedures and referrals are represented in downstream reporting.

Context / Why
ServiceRequest captures pending or ordered clinical actions and is a common export type.
Without a mapping, requested procedures are invisible to reporting and evidence bundles.

Acceptance Criteria
- Given a synthetic clinical records fixture containing FHIR ServiceRequest entries, when `healthdelta export ndjson` runs, then NDJSON `service_request` (or equivalent canonical) records are emitted with stable IDs, status, intent, code, authored date, and subject references.
- Given ServiceRequest entries that reference performers or organizations, when the export runs, then the NDJSON output retains those references (IDs or canonical link fields).
- Given CI runs on the change branch, when the `CI / Linux (non-iOS tests)` job completes, then NDJSON validation smoke and unit tests pass and upload their artifacts.

Out of Scope
- Scheduling workflows or operational task management.
- UI review workflows.

Notes
- Use synthetic-only fixtures.
- Align codes with existing terminology mapping patterns.
---
