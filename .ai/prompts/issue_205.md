---
Story
As a project operator,
I want the roadmap refreshed and a new issue set created,
So that the backlog reflects current priorities with traceable scope and proofs.

Context / Why
The roadmap and issue queue must stay synchronized so work remains issue-driven and auditable.

Acceptance Criteria
- Given the current roadmap, when it is refreshed, then `docs/plan.md` reflects the updated priority ordering and references the newly created issues.
- Given the new roadmap focus areas, when issues are created, then each issue exists in GitHub with the required template and linked in `docs/plan.md`.
- Given the updates, when CI runs, then workflow `CI` job `Linux (non-iOS tests)` passes to prove audit gating correctness.

Out of Scope
- Implementing any of the newly created roadmap items.
- Changing code or behavior beyond roadmap and issue metadata updates.

Notes
Use the standard issue template for each created issue and keep the roadmap share-safe.
---
