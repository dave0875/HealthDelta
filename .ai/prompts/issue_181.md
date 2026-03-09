---
Story
As an operator,
I want the unresolved reference report to break down clinical-record gaps,
So that I can prioritize fixes for missing subjects and cross-resource links.

Context / Why
Unresolved references are already tracked, but we need a clinical-record-specific view to guide hospital coverage work.

Acceptance Criteria
- Given synthetic clinical-record fixtures with missing subject or encounter links, when running `healthdelta report build`, then the unresolved reference output includes a clinical-record section with counts by resourceType and missing reference kind.
- The clinical-specific section is deterministic and share-safe.
- CI: `ci.yml` job `linux-tests` passes with new or updated unit tests covering the new output.

Out of Scope
- Implementing new identity resolution logic.
- Any UI dashboards or external analytics tooling.

Notes
- Update `docs/runbook_reports.md` to describe the new clinical unresolved reference section.
---
