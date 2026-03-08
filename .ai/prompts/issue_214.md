---
Story
As a maintainer,
I want the current repo-local closure and governance backfills committed under a single tracked issue,
So that the working tree is clean and the audit trail matches the already-closed GitHub work.

Context / Why
The current working tree contains repo-local closure work that aligns documentation and downstream tests for Issue #76 and repairs missing `.ai` audit artifacts for already-closed governance issues (#49, #52, #58, #62, #76, #87, #93, #94, #95, #99). Those changes should not remain as uncommitted local state because they increase the risk of tangling future issue work and make the repository harder to reconcile against GitHub.

Acceptance Criteria
- Given the current dirty working tree, when this issue is completed, then the changes are committed under a single issue-linked commit and the working tree is clean.
- Given Issue #76 closure work, when the commit is reviewed, then the medication docs and downstream test coverage updates are included.
- Given the closed governance issues with missing local audit artifacts, when the commit is reviewed, then the missing `.ai/sessions/` and `.ai/time/time.csv` entries are included.
- Given project governance, when this issue is executed, then `.ai/prompts/issue_N.md`, `.ai/sessions/`, and `.ai/time/time.csv` are updated for the active issue.

Out of Scope
- Changing product behavior beyond the already-applied local closure work.
- Reprioritizing roadmap issues or editing `docs/plan.md`.
- Closing or reopening unrelated GitHub issues.

Notes
- Keep scope strictly to capturing and committing the already-applied local changes.
---
