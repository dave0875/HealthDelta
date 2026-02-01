# Session 14 - 2026-02-01

Issue: #130

Goal
- Harden governance enforcement so rewrite/force-push conditions do not block validation runs.

Notes
- Refactored governance scripts to be rewrite-tolerant and degrade gracefully when commit ranges are missing.
- Changed CI policy step behavior to continue into tests and fail at the end with explicit policy-failure labeling.
- Added regression tests for rewrite-tolerant commit/PR issue checks.
- Added ADR on durable governance anchors and updated AGENTS/runbook references.

Local verification
- TZ=UTC python3 -m unittest tests/test_issue_footer.py -v
- TZ=UTC python3 -m unittest tests/test_pr_issue.py -v
- TZ=UTC python3 -m unittest tests/test_audit_artifacts.py -v
- TZ=UTC python3 -m unittest discover -s tests -v
