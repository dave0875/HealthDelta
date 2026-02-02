# Session 20 - 2026-02-01

Issue: #143

Goal
- Make auto tag-triggered ORIN deploy resilient to GHCR publish latency.

Notes
- Added a bounded wait loop in `.github/workflows/deploy_backend_orin.yml` to poll GHCR manifest availability before deploy.
- Added clear progress and timeout logging for image availability checks.
- Updated `docs/runbook_orin_deploy.md` to include the manifest-availability gate in verification behavior.

Local verification
- TZ=UTC python3 -m unittest tests/test_audit_artifacts.py -v
