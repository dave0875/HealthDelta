---
Story
As a collaboration lead,
I want a share-safe clinical records evidence manifest,
So that share bundles include auditable, non-PHI evidence for clinical mappings.

Context / Why
Clinical records mappings need proof artifacts that are safe to share and easy to review.

Acceptance Criteria
- Given a share bundle build, when clinical records outputs are present, then a share-safe evidence manifest is generated that summarizes resource counts, mapping coverage, and redaction status without PHI.
- Given the manifest output, when `healthdelta report build` or `healthdelta share bundle` runs, then the manifest is included in the bundle artifacts.
- Given the updates, when CI runs, then workflow `CI` job `Linux (non-iOS tests)` passes.

Out of Scope
- Publishing any clinical records content or raw exports.
- Modifying de-identification behavior beyond evidence manifest generation.

Notes
Evidence artifacts must remain share-safe and align with runbook expectations.
---
