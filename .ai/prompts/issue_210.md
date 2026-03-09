---
Story
As a clinical record integrator,
I want ImagingStudy resources mapped into canonical NDJSON,
So that imaging context is preserved in downstream analytics.

Context / Why
Clinical record exports often include ImagingStudy, and missing mappings reduce coverage and traceability for imaging workflows.

Acceptance Criteria
- Given a synthetic clinical records fixture containing an `ImagingStudy` resource with a linked patient, when `healthdelta export ndjson` runs, then a corresponding ImagingStudy NDJSON record is emitted with stable `id`, `status`, `subject.reference`, and `started` (when present).
- Given ImagingStudy `series` entries, when exported, then the NDJSON output includes a deterministic, share-safe series summary aligned with existing resource mapping conventions.
- Unit tests are added first (TDD) and validate field mapping + reference resolution using synthetic fixtures only.
- CI proof: `CI` workflow job `Linux (non-iOS tests)` and `Run NDJSON validation smoke`.

Out of Scope
- DICOM binary handling or rendering of imaging content.

Notes
- Ensure output remains share-safe and excludes PHI/PII.
---
