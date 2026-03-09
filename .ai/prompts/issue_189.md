---
Story
As a pipeline operator,
I want DiagnosticReport resources mapped into canonical NDJSON,
So that lab/imaging reports are represented in downstream analytics and summaries.

Context / Why
DiagnosticReport coverage is currently a known gap in the clinical records mapping.
Without it, lab and imaging report metadata is missing from share-safe exports and reports.

Acceptance Criteria
- Given a synthetic clinical records fixture containing FHIR DiagnosticReport entries, when `healthdelta export ndjson` runs, then an NDJSON `diagnostic_report` (or equivalent canonical) record is produced for each input report with stable IDs, dates, codes, and subject references.
- Given the same fixture, when NDJSON validation (`healthdelta export ndjson --validate` or `healthdelta ndjson validate`) runs, then the DiagnosticReport records pass schema validation with no missing required fields.
- Given CI runs on the change branch, when the `CI / Linux (non-iOS tests)` job completes, then the NDJSON validation smoke and unit tests pass and upload their artifacts.

Out of Scope
- Parsing or embedding full report narrative content beyond share-safe metadata.
- Changes to iOS export capture or HealthKit ingestion.

Notes
- Use synthetic-only fixtures; do not commit real exports.
- If a new canonical entity name is introduced, document it in `docs/plan.md` or a relevant mapping doc.
---
