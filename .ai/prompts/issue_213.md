---
Story
As a maintainer,
I want `docs/plan.md` reconciled to the live GitHub issue state,
So that the in-repo roadmap accurately reflects what is closed, active, and next.

Context / Why
`docs/plan.md` currently drifts from the actual GitHub tracker. For example, the plan still marks Issue #162 as active even though GitHub shows it closed, and the plan does not reflect the current open roadmap issues that now exist beyond the original Orin MMF slice. Without reconciliation, operators and autonomous work can choose the wrong next issue or report stale project status.

Acceptance Criteria
- Given the current GitHub issue tracker, when `docs/plan.md` is updated, then every issue explicitly listed in the plan has a status label that matches the live GitHub state.
- Given the current backlog, when the plan is updated, then the "Next issues" section links to the currently relevant open issues instead of stale or already-completed items.
- Given the updated plan, when a maintainer audits it against `gh issue list`, then the plan contains no issue listed as active if GitHub shows it closed.
- Given project governance, when this issue is executed, then `.ai/prompts/issue_N.md`, `.ai/sessions/`, and `.ai/time/time.csv` are updated for the active issue.

Out of Scope
- Creating or closing additional product issues beyond the minimum needed to reflect current tracker reality.
- Reprioritizing the backlog beyond what is necessary to remove stale status drift.
- Changing roadmap strategy outside `docs/plan.md`.

Notes
- Keep the issue narrowly scoped to reconciling the in-repo plan with the live GitHub tracker.
- Prefer the smallest diff that restores plan accuracy.
---
