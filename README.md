# HealthDelta

Incremental Apple Health + HealthKit + Clinical Records system with strict identity safety, auditability, and an issue-driven workflow.

## How we work
- All work is tracked by GitHub issues and implemented incrementally (small vertical slices).
- `main` stays releasable (trunk-based).
- TDD for non-trivial logic.
- Codex audit artifacts live in `.codex/` (no secrets).
- Every session is logged in `TIME.csv`.

## Repo layout (initial)
- `docs/`: architecture + threat model + core domain docs
- `.codex/`: prompts, sessions, and ADRs for auditability
- `ios/HealthDelta/`: iOS app (built on macOS)
- `mac/ingest/`: mac ingestion (DuckDB) tooling
- `tests/`: test suites (TDD)

