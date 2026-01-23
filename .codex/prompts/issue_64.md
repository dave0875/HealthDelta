Issue: https://github.com/dave0875/HealthDelta/issues/64

Scope / intent (immutable)
- Add reliable, share-safe progress indicators for long-running CLI commands.
- Implement a centralized progress framework and global CLI flags:
  - `--progress {auto,always,never}` (default `auto`)
  - `--log-progress-every N` seconds (default 5)
- Integrate progress into at least:
  - `healthdelta ingest`
  - `healthdelta export ndjson`
- Add tests to validate progress output behaviors without PHI/PII.

Acceptance criteria (restated)
- Long-running commands emit progress (interactive for TTY, line-based otherwise).
- Progress never prints PHI/PII (only counts, sizes, durations, step names).
- `--progress never` suppresses progress output (still prints final summary).
- Non-TTY mode produces periodic line-based progress output.
- Progress framework is centralized in `healthdelta/progress.py` and heavy deps are lazily imported.

