---
Story
As an operator,
I want source system attribution in a share-safe form,
So that data provenance is visible without exposing PII.

Context / Why
Operators need to distinguish records from different hospital systems.

Acceptance Criteria
- Derive a deterministic, non-PII source_system tag (e.g., hashed identifier.system or meta.source).
- Tag appears in NDJSON and reports.
- Tests verify stable tagging and absence of raw identifiers.

Out of Scope
- Human-readable hospital names.
---
