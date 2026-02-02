# Session 17 - 2026-02-02

Issue: #164

Goal
- Close ORIN persistent data-plane gap by wiring host bind mount and proving mount/sentinel persistence in deploy verification.

Notes
- Added ORIN compose bind mount `/opt/healthdelta/data:/app/data`.
- Updated ORIN deploy script to idempotently create/check writable data dir and fail with actionable remediation.
- Extended verify script with explicit data-plane checks:
  - inspect mount source/destination
  - sentinel roundtrip in container + host visibility
  - sentinel persistence across service restart
- Updated ORIN deploy/CD runbooks to require/prove data-plane checks.
- Added tests for compose mount and verify-script invariants.

Local verification
- TZ=UTC python3 -m unittest tests/test_orin_data_plane_config.py -v
- TZ=UTC python3 -m unittest tests/test_audit_artifacts.py -v
