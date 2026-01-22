# Issue #23 — Plan refresh: extend backlog beyond #22 (immutable prompt)

Issue: https://github.com/dave0875/HealthDelta/issues/23

Host constraint (authoritative execution rule)
- All repository mutations occur ONLY on Ubuntu host `GORF`.
- macOS runner is used ONLY via GitHub Actions for Xcode work; no repo mutation on macOS.

## Acceptance criteria (restated)

- Update `docs/plan.md` to:
  - mark Issues #17–#22 as completed
  - add links and one-line intent for Issues #23–#32
  - keep the document share-safe (no secrets, no local absolute paths, no PII)
- Add local issue artifact: `docs/issues/ISSUE-0023.md`.
- Add session log + review artifact + `TIME.csv` row.
- CI green (Linux tests + macOS Xcode job with `ios-xcresult` artifact) before closing.

## Plan

1) Update `docs/plan.md` to include a completed section and the next 10 issues.
2) Add `docs/issues/ISSUE-0023.md`.
3) Add session + review + TIME.csv entries.
4) Run local tests, push, wait for CI, comment and close Issue #23.

