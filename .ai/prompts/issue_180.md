---
Story
As an operator,
I want export profiling to emit a share-safe clinical record inventory artifact,
So that I can baseline hospital record coverage before running ingest/pipeline.

Context / Why
We already profile export directories, but clinical record bundles are high-impact and need an explicit, deterministic inventory before processing.

Acceptance Criteria
- Given an export directory with Apple Health clinical records, when running `healthdelta export profile`, then a new deterministic artifact `clinical_inventory.json` is produced with counts by FHIR resourceType and CDA section.
- The artifact is share-safe (no free-text PHI) and uses stable, sorted keys.
- When no clinical records are present, the artifact exists and reports zero counts.
- CI: `ci.yml` job `linux-tests` passes with new or updated unit tests covering the artifact.

Out of Scope
- Any changes to pipeline orchestration or de-identification.
- Changes to iOS incremental export format.

Notes
- Update `docs/runbook_profile.md` with the new artifact description.
---
