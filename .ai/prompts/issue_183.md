---
Story
As an operator,
I want a share-safe coverage matrix and gap report for FHIR clinical record resources,
So that I can see what is mapped vs. missing before expanding coverage.

Context / Why
Clinical record exports include multiple FHIR resource types. We need an objective, share-safe inventory that shows mapped coverage and gaps before adding new mappings.

Acceptance Criteria
- Given a share-safe clinical export fixture, when I run the coverage report command, then it produces a share-safe `coverage_matrix.json` artifact listing FHIR resource types, record counts, and whether each has a canonical mapping.
- Given the same fixture, when I run the command, then it produces a share-safe `coverage_matrix.md` summary with the top unmapped resources and the exact fixture sample counts.
- A unit test verifies the coverage report counts for the fixture.
- CI proof: GitHub Actions `CI` workflow, job `Linux (non-iOS tests)`, uploads the coverage artifacts as part of `linux-unittest`.

Out of Scope
- Implementing new canonical mappings.
- Changing production export behavior.

Notes
- Keep the artifacts share-safe (no raw record payloads).
- If a new CLI entrypoint is added, document it in the relevant runbook.
---
