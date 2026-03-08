---
Story
As a project maintainer,
I want a share-safe coverage inventory and prioritized roadmap for hospital clinical records,
So that the next resource-type expansion is grounded in evidence and risk-aware planning.

Context / Why
Clinical records coverage is expanding beyond current FHIR/CDA handling. We need a deterministic, share-safe inventory of what is present and missing to prioritize the next implementation slices and avoid scope creep.

Acceptance Criteria
- Given an export/profile run, when the coverage inventory is produced, then a deterministic, share-safe artifact lists FHIR resourceTypes, CDA sections, and observed counts.
- Given the inventory, when the roadmap slice is drafted, then docs/plan.md references this issue and lists a prioritized set of next clinical record targets.
- Given the artifacts, when reviewed, then no PII/PHI content is present (metadata only).

Out of Scope
- Implementing new FHIR/CDA export support beyond current capabilities.
- Changing ingest or de-identification logic.

Notes
Use existing export profiling outputs where possible; avoid duplicating expensive scans.
---
