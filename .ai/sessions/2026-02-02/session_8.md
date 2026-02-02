# Session 8 - 2026-02-02

Issue: #154

Goal
- Fix release image build context so ORIN endpoint smoke fixtures are present in-container.

Notes
- Moved deploy smoke fixture source to `deploy/fixtures/profile_export` (included by Docker build context).
- Updated Dockerfile and ORIN deploy/rollback verification paths to `/app/deploy/fixtures/profile_export`.
- Updated deploy workflow endpoint sample capture payload paths.

Local verification
- TZ=UTC python3 -m unittest tests/test_backend_server.py -v
- TZ=UTC python3 -m unittest tests/test_audit_artifacts.py -v
- TZ=UTC python3 -m unittest discover -s tests -v
