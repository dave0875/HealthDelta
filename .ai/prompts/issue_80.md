---
Story
As a maintainer,
I want de-identification to scrub free-text fields in FHIR resources,
So that narrative strings don’t leak PHI in share-safe outputs.

Context / Why
Narrative text can contain names or identifiers.

Acceptance Criteria
- For supported FHIR resource types, text/narrative fields are replaced with a deterministic placeholder.
- No regression in schema validation.
- Tests prove text fields are redacted.

Out of Scope
- NLP-based PII detection.
---
