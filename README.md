# HealthDelta

Incremental Apple Health + HealthKit + Clinical Records system with strict identity safety, auditability, and an issue-driven workflow.

## How we work
- All work is tracked by GitHub issues and implemented incrementally (small vertical slices).
- `main` stays releasable (trunk-based).
- TDD for non-trivial logic.
- Commit messages must include an Issue footer (`Issue: #NN`); CI enforces this.
- Each issue gets one immutable prompt at `.ai/prompts/issue_<n>.md`; follow-up prompts are append-only.
- Each work session records a session note under `.ai/sessions/YYYY-MM-DD/session_<n>.md` and appends `.ai/time/time.csv`.
- Completed issues also add a review artifact under `docs/reviews/`.
- CI governance checks enforce issue footers, PR issue metadata, audit artifacts, prompt immutability, and managed worktree policy.
- Tests run in UTC (`TZ=UTC`) to keep deterministic timestamps consistent across environments.
- Codex audit artifacts live in `.ai/` (no secrets).

## Repo layout (initial)
- `docs/`: architecture + threat model + core domain docs
- `.ai/`: prompts, sessions, and ADRs for auditability
- `ios/HealthDelta/`: iOS app (built on macOS)
- `mac/ingest/`: mac ingestion (DuckDB) tooling
- `tests/`: test suites (TDD)
