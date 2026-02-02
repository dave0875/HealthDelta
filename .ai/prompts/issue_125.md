---
Story
As a user,
I want trend analysis over key clinical measures,
So that changes over time are easy to interpret.

Context / Why
Trend analysis is a core mission capability and should follow once summary/risk vertical slices are proven.

Acceptance Criteria
- Given longitudinal observations, when trend analysis runs, then outputs include time-windowed trend direction and confidence markers.
- Given missing/sparse data, when trend analysis runs, then outputs explicitly report insufficiency instead of guessing.
- Given share-safe requirements, when trend outputs are emitted, then no direct identifiers are present.
- Given test fixtures, when CI runs, then deterministic trend outputs are verified across repeated runs.

Out of Scope
- Predictive diagnosis.
- Real-time streaming ingestion.

Notes
- Keep first version focused on a small fixed metric set.
---
