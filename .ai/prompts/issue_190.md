---
Story
As a pipeline operator,
I want DocumentReference resources mapped into canonical NDJSON,
So that clinical document metadata is captured without leaking PHI.

Context / Why
Clinical exports include DocumentReference entries that point to letters, PDFs, and imaging summaries.
Without a mapping, document metadata is lost and downstream evidence bundles are incomplete.

Acceptance Criteria
- Given a synthetic clinical records fixture containing FHIR DocumentReference entries, when `healthdelta export ndjson` runs, then an NDJSON `document_reference` (or equivalent canonical) record is produced with stable IDs, dates, type codes, and subject references.
- Given DocumentReference entries containing attachment metadata, when the export runs, then any attachment content is excluded and only share-safe metadata (content type, title, size, hash if available) is emitted.
- Given CI runs on the change branch, when the `CI / Linux (non-iOS tests)` job completes, then NDJSON validation smoke and unit tests pass and upload their artifacts.

Out of Scope
- Exporting or storing binary attachments.
- OCR or content extraction from document payloads.

Notes
- Keep metadata share-safe per `docs/runbook_deid.md`.
- If new schema fields are needed, update tests and NDJSON validation fixtures.
---
