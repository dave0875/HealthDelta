# issue_3

Issue: https://github.com/dave0875/HealthDelta/issues/3

Prompt (verbatim)

```
AUTHORITATIVE CODEX SUPER-PROMPT
(Project Continuity + Issue #2 Follow-Up + Governance Lock-In)

Objectives (in order):
1) Record post-hoc execution constraints and governance rules discovered during Issue #2
2) Permanently document the Codex operating methodology for all future work
3) Complete Issue #2 strictly within its original scope

SECTION B — CODEX GOVERNANCE (GLOBAL, PERSISTENT)

Codex Prompt Discipline:
- Each GitHub Issue N has exactly one immutable prompt:
  `.codex/prompts/issue_N.md`
- Once work begins, `issue_N.md` is read-only and never edited.
- Post-hoc clarifications or execution constraints are recorded as:
  `.codex/prompts/issue_N_followup_X.md`, where X ∈ [1–9].
- Follow-ups are append-only and must state explicitly that they do NOT change scope.
- Reaching follow-up 9 is a forcing function to open a new GitHub issue.
- Numeric forks such as `issue_N.1`, `issue_N_part2`, etc. are prohibited.

Execution Discipline:
- No code, workflow, or documentation changes without a GitHub Issue capturing WHY.
- All CI work must produce observable, persisted artifacts.
- Self-hosted runners are authoritative; cloud runners must not substitute silently.
- Ambiguity pauses execution and requires clarification before proceeding.

These rules are binding on all future Codex sessions and must be treated as project law.
```

