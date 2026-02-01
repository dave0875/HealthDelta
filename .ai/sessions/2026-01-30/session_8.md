# Session 8 — 2026-01-30

Issue: #93

Goal
- Enforce single Issue number across commit set in CI.

Notes
- Extended issue footer checker to reject multiple Issue numbers.
- Added tests for Issue extraction and single-Issue enforcement.

Local verification
- `TZ=UTC python3 -m unittest discover -s tests -p 'test_*.py' -v`
