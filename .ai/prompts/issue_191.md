---
Story
As a pipeline operator,
I want CarePlan and Goal resources mapped into canonical NDJSON,
So that ongoing care intent and targets are represented in analytics.

Context / Why
Care plans and goals inform longitudinal context and are required for a complete clinical picture.
Without them, summaries miss planned interventions and target outcomes.

Acceptance Criteria
- Given a synthetic clinical records fixture containing FHIR CarePlan and Goal entries, when `healthdelta export ndjson` runs, then NDJSON records are emitted for care plans and goals with stable IDs, status, intent, dates, and subject references.
- Given CarePlan entries with referenced Goal IDs, when the export runs, then the NDJSON output links care plans to goals using stable identifiers.
- Given CI runs on the change branch, when the `CI / Linux (non-iOS tests)` job completes, then NDJSON validation smoke and unit tests pass and upload their artifacts.

Out of Scope
- CarePlan narrative expansion or document attachments.
- UI or operator review workflows.

Notes
- Keep identifiers deterministic for dedupe/replay safety.
- Use synthetic-only fixtures.
---
