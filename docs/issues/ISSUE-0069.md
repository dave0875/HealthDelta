# ISSUE-0069: CLI: progress indicators for identity/profile/validate/pipeline

GitHub: https://github.com/dave0875/HealthDelta/issues/69

## Objective
Add share-safe progress indicators to remaining long-running CLI commands that can otherwise appear stalled on large exports.

## Context / Why
Issues #64 and #66 added a centralized progress framework and integrated most heavy workflows, but some commands (identity build, export profiling, NDJSON validation, pipeline run) can still run silently for >5 seconds.

## Acceptance Criteria
- `healthdelta identity build` emits progress (phases + counters/rate) without PHI/PII.
- `healthdelta export profile` emits progress during directory scans and per-file work without printing input paths.
- `healthdelta export validate` emits progress during per-file validation and record scanning.
- `healthdelta pipeline run` emits progress for high-level phases without changing share-safe stdout output.
- `--progress never` suppresses progress lines but still prints a final phase summary to stderr.
- Tests validate progress output for at least one newly-instrumented command in non-TTY mode.

## Test Plan
- Local: `python3 -m unittest discover -s tests -p 'test_*.py' -v`
- CI: `CI` workflow green
