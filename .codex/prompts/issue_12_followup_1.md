# Issue #12 Follow-up 1 (additive; does NOT change scope)

Issue #12: https://github.com/dave0875/HealthDelta/issues/12

References
- Immutable prompt (read-only): `.codex/prompts/issue_12.md`

Statement (mandatory)
- This is an additive request discovered during execution; it does NOT change Issue #12 acceptance criteria.
- The add-on described here will be implemented as a separate GitHub issue: Issue #13.

Add-on requirement (Doctor’s Note)
- Add a deterministic, share-safe “doctor’s note” style summary produced from the DuckDB database.
- Output should be one-screen (≈25 lines), byte-stable across reruns for the same DB, and contain no PII.
- This is explicitly not part of Issue #12; it is a new deliverable in Issue #13.

