Issue: https://github.com/dave0875/HealthDelta/issues/66

Scope / intent (immutable)
- Extend the progress framework (Issue #64) across remaining long-running CLI commands:
  - DuckDB build/import
  - Reports and doctor note generation
  - De-identification
  - Share bundle creation
  - Operator `run all` nested progress

Acceptance criteria (restated)
- All long-running commands emit progress via `healthdelta.progress` without PHI/PII.
- `healthdelta run all` shows overall phases + sub-step progress.
- Tests cover at least one additional command’s progress output.

