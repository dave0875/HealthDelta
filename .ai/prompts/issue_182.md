---
Story
As a collaborator,
I want share bundles to include hospital-record coverage evidence artifacts,
So that I can validate clinical record progress without raw exports.

Context / Why
Share bundles are the primary collaboration artifact, but they lack explicit hospital-record coverage evidence.

Acceptance Criteria
- Given a share bundle built from a run that includes clinical records, when running `healthdelta share bundle`, then the bundle contains the latest `coverage.json`, `coverage.md`, and `clinical_inventory.json` artifacts.
- Given a share bundle built without clinical records, the bundle still includes empty but valid coverage artifacts (zero counts).
- The share bundle manifest lists the added artifacts with sizes and sha256 hashes.
- CI: `ci.yml` job `linux-tests` passes with new or updated unit tests covering share bundle inclusion.

Out of Scope
- Changing the share bundle format to include raw exports.
- Any changes to deployment workflows.

Notes
- Coordinate artifact naming with Issues #179 and #180.
---
