---
Story
As a clinical record integrator,
I want Device resources mapped into canonical NDJSON,
So that implanted or referenced devices are traceable in downstream analysis.

Context / Why
Device records appear in clinical exports (implants, equipment, identifiers) and are currently unmapped, reducing coverage.

Acceptance Criteria
- Given a synthetic clinical records fixture containing a `Device` resource with a linked patient, when `healthdelta export ndjson` runs, then a Device NDJSON record is emitted with stable `id`, `patient.reference`, and `status` when present.
- Given Device identifiers and type/manufacturer fields, when exported, then values are represented deterministically and follow share-safe redaction rules where applicable.
- Unit tests are added first (TDD) and validate field mapping + reference resolution using synthetic fixtures only.
- CI proof: `CI` workflow job `Linux (non-iOS tests)` and `Run NDJSON validation smoke`.

Out of Scope
- Device data ingestion from non-clinical sources or new PHI redaction policies.

Notes
- Ensure output remains share-safe and excludes PHI/PII.
---
