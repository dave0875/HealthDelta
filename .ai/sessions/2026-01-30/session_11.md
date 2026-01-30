# Session 11 — 2026-01-30

Issue: #96

Goal
- Enforce prompt immutability for issue prompts.

Notes
- Added prompt immutability checker and CI step.
- Added unit tests for prompt path rules.

Local verification
- `TZ=UTC python3 -m unittest discover -s tests -p 'test_*.py' -v`
