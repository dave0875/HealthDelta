Issue: https://github.com/dave0875/HealthDelta/issues/69

Scope / intent (immutable)
- Extend CLI progress indicators (Issues #64/#66) to remaining long-running commands:
  - `healthdelta identity build`
  - `healthdelta export profile`
  - `healthdelta export validate` / NDJSON validation
  - `healthdelta pipeline run`

Acceptance criteria (restated)
- These commands emit share-safe progress (no PHI/PII; no input paths).
- `--progress never` suppresses interactive/line progress but still prints a final phase summary to stderr.
- Tests cover progress output for at least one newly-instrumented command in non-TTY mode.
