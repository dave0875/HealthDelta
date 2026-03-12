# Issue #236 Prompt

Issue: #236
Title: ORIN-backed patient scope and accurate overview progress state

Immutable execution prompt recorded at start of work.

Scope
- Add a share-safe ORIN patient-scope endpoint derived from the current dataset.
- Use that endpoint on iPhone so patient scope options reflect live ORIN patient buckets instead of only device-local identity state.
- Separate true in-flight activity from completed status messaging so the overview card spinner only appears while work is active.

Goals
- Return deterministic patient scope options from ORIN without exposing PII.
- Preserve existing local/manual patient fallback behavior when ORIN scope metadata is unavailable.
- Remove the misleading spinner from completed upload/refresh states while keeping status text visible.
- Verify the behavior with backend and iOS tests before closing the issue.

Constraints
- No secrets in `.ai/`.
- Use TDD for the new endpoint/client/state logic.
- Keep `main` releasable and verify CI + Release before closure.
