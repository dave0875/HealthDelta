Issue: https://github.com/dave0875/HealthDelta/issues/41

Scope / intent (immutable)
- Publish Linux unit test output as a persisted CI artifact so failures are easier to triage and evidence is standardized, matching the macOS `ios-xcresult` artifact approach.

Acceptance criteria (restated)
- Update `.github/workflows/ci.yml` Linux job to:
  - capture unit test output to an artifact (log file)
  - upload it via `actions/upload-artifact@v4` with a deterministic artifact name
  - (JUnit if feasible without introducing a new test framework/dependency)
- Record audit artifacts (prompt/session/review/TIME.csv).
- CI green required before closing.

Plan
1) Adjust Linux test step to:
   - write `artifacts/linux/unittest.log`
   - preserve the unittest exit code (so we can upload artifacts even on failure)
2) Add an `if: always()` artifact upload step with a stable name (e.g., `linux-unittest`).
3) Add a final step that fails the job if the test exit code was non-zero.
4) Run local tests; push; verify CI artifacts exist; comment + close.

Constraints
- No new test frameworks/dependencies solely for JUnit output (Issue #41 out of scope).
- No secrets/PHI/PII in logs or artifacts; tests are synthetic-only.
