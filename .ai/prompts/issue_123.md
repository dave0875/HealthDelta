---
Story
As an operator,
I want a first end-to-end Orin vertical slice (ingest -> de-id -> summary API),
So that production readiness can be proven with a minimal user-visible outcome.

Context / Why
A vertical slice de-risks architecture by proving the full chain on target hardware, not just isolated components.

Acceptance Criteria
- Given a synthetic fixture set, when the slice runs on Orin, then a share-safe summary response is produced through backend API.
- Given de-id policy, when summary generation executes, then banned PHI tokens are absent from logs and outputs.
- Given traceability requirements, when summary output is returned, then source references/citations to ingested records are included.
- Given deployment proof needs, when CI for this slice runs, then artifacts include run logs and output samples.

Out of Scope
- Risk scoring logic.
- Trend and Q&A features.

Notes
- Keep scope minimal and deterministic.
---
