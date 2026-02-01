---
Story
As a maintainer,
I want governance enforcement to be rewrite-tolerant and non-blocking to validation execution,
So that policy intent is preserved without brittle CI failures during rebases/force-pushes.

Context / Why
Current governance checks rely on git history assumptions that can fail under force-push, rebase, or shallow-history conditions. Governance should enforce the same intent while degrading gracefully and ensuring tests still run.

Acceptance Criteria
- Given rewritten or missing commit ranges, when governance scripts run, then they do not crash and emit actionable fallback explanations.
- Given CI runs on Linux/macOS, when governance checks fail, then test/build validation still executes and failures are labeled as policy failures.
- Given commit-level checks, when range resolution is unreliable, then enforcement falls back to durable anchors (PR metadata, merge commit, release/tag metadata, and `.ai/` artifacts) without increasing strictness.
- Given documentation updates, when this issue is complete, then ADR + runbook/AGENTS reflect rewrite-tolerant enforcement and durable anchors.
- Given regression tests, when CI runs, then rewritten-history scenarios are covered and pass deterministically.

Out of Scope
- Introducing new governance requirements.
- Manual approvals or process-only controls.

Notes
- Preserve existing governance intent; harden implementation only.
---
