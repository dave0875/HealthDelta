# Issue #235 Prompt

Issue: #235
Title: Expand iPhone HealthKit export coverage beyond step count

Immutable execution prompt recorded at start of work.

Scope
- Replace the current step-count-only iPhone export behavior with a broader HealthKit export set.
- Preserve the existing iPhone export layout and ORIN upload path unless a minimal compatible evolution is required.
- Keep aliases/UI polish separate unless directly required to expose or validate the broader exported data.

Goals
- Request HealthKit authorization for a defined multi-type set rather than only step count.
- Export deterministic rows for quantity, category, and workout samples in the supported set.
- Preserve the broader signals through iOS export, ORIN upload, DuckDB ingestion, and reporting compatibility.
- Document the supported types, known exclusions, and any safe field-selection constraints.

Constraints
- No secrets in `.ai/`.
- Use TDD for non-trivial logic.
- Keep `main` releasable and verify CI + Release before closure.
