---
Story
As a clinical record integrator,
I want Specimen resources mapped into canonical NDJSON,
So that diagnostic and lab provenance can be traced across records.

Context / Why
Specimen metadata is commonly referenced by DiagnosticReport/Observation and is needed for evidence completeness.

Acceptance Criteria
- Given a synthetic clinical records fixture containing a `Specimen` resource linked to a patient and diagnostic report, when `healthdelta export ndjson` runs, then a Specimen NDJSON record is emitted with stable `id`, `subject.reference`, and collected/received timing when present.
- Given Specimen identifiers and type/coding, when exported, then codes are preserved in a deterministic, share-safe representation aligned to existing mapping conventions.
- Unit tests are added first (TDD) and validate field mapping + reference resolution using synthetic fixtures only.
- CI proof: `CI` workflow job `Linux (non-iOS tests)` and `Run NDJSON validation smoke`.

Out of Scope
- New terminology normalization beyond existing code system handling.

Notes
- Ensure output remains share-safe and excludes PHI/PII.
---
