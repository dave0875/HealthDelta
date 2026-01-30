# Session 9 — 2026-01-30

Issue: #94

Goal
- Ensure PR metadata Issue matches commit Issue footer.

Notes
- Added PR Issue metadata checker and CI step.
- Added unit test for PR issue extraction.
- Extended issue footer checker with --print-issue.

Local verification
- `TZ=UTC python3 -m unittest discover -s tests -p 'test_*.py' -v`
