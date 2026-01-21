# Issue #16 — Living plan/backlog + local issue artifact template (immutable prompt)

Issue: https://github.com/dave0875/HealthDelta/issues/16

Host constraint (authoritative execution rule)
- All repository mutations occur ONLY on Ubuntu host `GORF`.
- macOS runner is used ONLY via GitHub Actions for Xcode work; no repo mutation on macOS.

## Acceptance criteria (restated)

- Add a living plan/backlog document in the repo (share-safe) that summarizes current capabilities and lists the next 5–10 logical issues in priority order.
- Add a local issue artifact template and create a local artifact entry for Issue #16.
- The plan/backlog references the corresponding GitHub issues by URL.
- No secrets and no PII in any new docs.
- Tests pass locally; CI is green; close Issue #16 with CI evidence.

## Implementation plan

1) Create `docs/plan.md`
   - short summary of current capability
   - prioritized next-issues list (Issues #17–#22) with GitHub URLs
2) Create local issue artifact directory `docs/issues/`
   - `docs/issues/README.md` with a simple template
   - `docs/issues/ISSUE-0016.md` local artifact for Issue #16
3) Update `AGENTS.md` to reference `docs/plan.md`.
4) Add audit artifacts:
   - `.codex/sessions/YYYY-MM-DD/session_16.md`
   - `docs/reviews/YYYY-MM-DD_16.md`
   - `TIME.csv` entry
5) Run tests, push, verify CI green, comment/close Issue #16.

