# ISSUE-0064: CLI: progress indicators + flags (framework + first integrations)

GitHub: https://github.com/dave0875/HealthDelta/issues/64

## Objective
Add reliable progress indicators to HealthDelta CLI commands that may process large datasets, using a centralized framework and consistent flags.

## Context / Why
Long-running operations (export parsing, staging, hashing) currently run silently, which is a usability and operational reliability bug. Progress output must be visible in terminals and logs, while remaining share-safe (no PHI/PII).

## Acceptance Criteria
- `--progress auto|always|never` (default `auto`) is implemented and affects all progress output.
- `--log-progress-every N` (default 5 seconds) rate-limits line-based progress updates.
- Progress output is share-safe (counts/sizes/durations only; no identifying text).
- Centralized progress abstraction exists in `healthdelta/progress.py` and is used by commands.
- Integrations in this issue:
  - `healthdelta ingest` shows progress across major phases.
  - `healthdelta export ndjson` shows progress across major phases.
- Tests validate:
  - progress output appears in non-TTY mode when enabled
  - `--progress never` suppresses progress output
  - progress module avoids heavy imports at import-time

## Non-Goals
- Full integration into every remaining command (tracked in follow-on issues).

## Test Plan
- Local: `python3 -m unittest discover -s tests -p 'test_*.py' -v`
- CI: `CI` workflow green

## Rollback Plan
- Revert progress framework and integrations.

