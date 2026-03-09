---
Story
As an operator,
I want share-safe hospital record coverage artifacts from report builds,
So that I can quantify clinical record gaps without exposing PHI.

Context / Why
Clinical record coverage is expanding, but we lack a deterministic, share-safe coverage summary to guide roadmap decisions and validate progress.

Acceptance Criteria
- Given synthetic clinical-record fixtures with multiple FHIR resource types and at least one CDA section, when running `healthdelta report build`, then new deterministic `coverage.json` and `coverage.md` artifacts are produced with counts by resourceType and CDA section.
- Given identical inputs, re-running the report produces byte-identical `coverage.json` and `coverage.md` artifacts.
- Given missing clinical records, the coverage artifacts explicitly indicate zero counts (no crash).
- CI: `ci.yml` job `linux-tests` passes with new or updated unit tests covering coverage artifacts.

Out of Scope
- Any UI dashboards or external analytics integrations.
- Changes to iOS export format.

Notes
- Artifacts must remain share-safe and avoid PHI/PII.
- Update `docs/runbook_reports.md` with the new artifacts.
---
