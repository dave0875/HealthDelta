Issue: https://github.com/dave0875/HealthDelta/issues/33

Scope / intent (immutable)
- Refresh `docs/plan.md` so it reflects completed work (#23–#32) and clearly states the next 10 prioritized issues (#33–#42).
- Produce the required local, share-safe audit artifacts for Issue #33 (prompt, local issue artifact, session log, review, TIME.csv).

Acceptance criteria (restated)
- Update `docs/plan.md` to:
  - mark Issues #23–#32 as completed
  - add Issues #33–#42 with 1–2 line descriptions each
  - keep ordering deterministic and consistent with project goals
- Add `docs/issues/ISSUE-0033.md`.
- Record immutable prompt `.codex/prompts/issue_33.md` (this file).
- Record session log + review artifact; update `TIME.csv`.
- Keep CI green before closing (Linux tests + macOS Xcode job).

Plan
1) Pull titles/bodies for Issues #33–#42 and summarize each in `docs/plan.md` (deterministic ordering by issue number).
2) Move Issues #23–#32 from “Next” to “Completed” in `docs/plan.md`.
3) Add local issue artifact `docs/issues/ISSUE-0033.md`.
4) Run local Linux tests (`python3 -m unittest ...`).
5) Run AI-on-AI review via local Ollama and write `docs/reviews/2026-01-22_33.md`.
6) Commit + push; wait for CI; then update session log with CI run link and close Issue #33 with evidence.

Determinism rules
- `docs/plan.md` uses stable ordering (issue number order within sections).
- Keep formatting stable (consistent headings/bullets; no time-varying content).

Privacy rules
- All artifacts are share-safe and must not include PII/PHI or absolute local paths.

