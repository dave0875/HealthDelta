# issue_6

Issue: https://github.com/dave0875/HealthDelta/issues/6

Prompt (verbatim)

```
Open a NEW GitHub issue (#6) using the story template.

Title:
De-identification: share-safe staging copies for export.xml + export_cda.xml + clinical-records/*.json

Story:
As a HealthDelta maintainer,
I want a deterministic de-identification step that produces a parallel, share-safe dataset from staged exports,
so that we can debug and collaborate using real export structures without exposing PII.

Context (real export shape):
- export.xml is large HealthKit XML
- export_cda.xml is huge CDA ClinicalDocument and includes patient header fields (name/birthTime/etc)
- clinical-records/*.json are single FHIR resources (mostly Observation)

Acceptance Criteria:
- Add CLI command:
  `healthdelta deid --input data/staging/<run_id> --identity data/identity --out data/deid/<run_id>/`
- Output mirrors staging layout under `data/deid/<run_id>/` and includes:
  - de-identified manifest.json + layout.json (redact absolute paths; preserve hashes/sizes)
  - de-identified export.xml (if present)
  - de-identified export_cda.xml (if present)
  - de-identified clinical-records/*.json (if present)
- Stable pseudonym mapping:
  - Derive stable mapping from `data/identity/people.json`
  - Write `mapping.json` containing only canonical_person_id -> "Patient N"
  - Never include original names or identifiers in mapping.json
- De-id rules (MVP):
  1) Replace known person name strings with "Patient N" for:
     - "First Last" and "Last, First"
  2) CDA header:
     - De-identify patientRole/patient/name content
     - Redact birthTime value (and document exactly how)
     - Document what is NOT covered yet
  3) FHIR JSON:
     - De-identify obvious patient name fields if present (e.g., Patient.name display forms)
     - Keep this minimal; do not attempt full PII scrubbing in every field
- Determinism:
  - same input + same identity -> same Patient N assignment and stable output
- Tests:
  - Synthetic fixtures only (no real health data committed)
  - Include tiny synthetic CDA + tiny synthetic FHIR resource(s)
  - Verify output contains no original synthetic names and no original synthetic birth date values
- Docs:
  - Add `docs/runbook_deid.md` and reference it from AGENTS.md
- Engineering discipline:
  - All repo mutations on GORF only
  - Create `.codex/prompts/issue_6.md` (immutable); followups issue_6_followup_X.md (X=1–9)
  - Update TIME.csv and add session/review artifacts
- Close Issue #6 only when CI is green.

Out of scope:
- Full FHIR-wide PII field scrub
- NDJSON schema
- DuckDB ingestion/summaries
```

