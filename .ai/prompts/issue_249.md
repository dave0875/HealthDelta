Issue #249: Fix FHIR export validation for patient references, null optional fields, and id-less resources

Source of truth: GitHub Issue #249

Scope:
- Normalize patient.reference as a fallback subject_reference for canonical clinical rows.
- Omit optional JSON-null fields from canonical FHIR NDJSON rows.
- Generate deterministic non-empty source_id values for id-less FHIR resources without exposing payload content.
- Add focused regression coverage proving normalized output passes NDJSON validation.

Non-goals:
- No streaming-memory refactor.
- No malformed CDA repair.
- No backend deployment changes.
