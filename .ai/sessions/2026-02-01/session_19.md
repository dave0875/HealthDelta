# Session 19 - 2026-02-01

Issue: #140

Goal
- Fix ORIN deploy verify invocation to avoid exit 126 permission failures.

Notes
- Updated `scripts/cd/orin_deploy_backend.sh` to run `orin_verify_backend.sh` via `bash`.
- This removes dependency on execute-bit state in runner checkout while preserving verification behavior.

Local verification
- TZ=UTC python3 -m unittest tests/test_audit_artifacts.py -v
