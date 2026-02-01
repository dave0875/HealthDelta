---
Story
As a maintainer,
I want subject resolution to recognize subject.identifier and Patient.identifier mappings,
So that multi-system linkage improves without PII.

Context / Why
Epic/MyChart data often uses identifier systems rather than Patient/<id> references.

Acceptance Criteria
- Given FHIR resources with subject.identifier, identity resolution matches to known Patient identifiers when available.
- Deterministic behavior when multiple candidates exist (choose "unresolved" unless unambiguous).
- Tests for subject.identifier and fallback logic.

Out of Scope
- Probabilistic matching.
---
