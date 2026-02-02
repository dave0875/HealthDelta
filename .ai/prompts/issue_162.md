# Issue #162 Prompt (Immutable)

Implement ORIN backend benchmark artifacts and regression threshold enforcement.

Scope:
- Add a dedicated ORIN benchmark workflow that runs on labels `[self-hosted, linux, orin]`.
- Collect deterministic benchmark metrics for backend `/summary`, `/qa`, and CLI pipeline run timings.
- Persist machine-readable JSON and operator-facing Markdown artifacts.
- Add threshold enforcement with explicit metric/threshold/observed failure messages.
- Document workflow usage, threshold location, and local reproduction in ORIN deployment runbook.
- Add unit tests for threshold checker logic.

Constraints:
- Synthetic/share-safe inputs only.
- No new governance rules.
- Keep implementation bounded to benchmark proof + threshold guardrails.
