# ISSUE-0048: CD: Backend service skeleton + operational endpoints (/healthz, /version)

GitHub: https://github.com/dave0875/HealthDelta/issues/48

## Objective
Add a minimal, share-safe backend HTTP service suitable for container deployment and automated post-deploy verification on ORIN.

## Context / Why
End-to-end CD needs a deployable backend target with strong verification. A minimal health/version service provides a safe foundation for deployment automation without introducing PHI/PII handling.

## Acceptance Criteria
- `/healthz` returns HTTP 200 and a small JSON body indicating healthy.
- `/version` returns JSON including at least `version` and `git_sha`.
- Backend container image builds and starts the service deterministically.
- Local dev compose brings up the service and the endpoints are reachable on a documented port.
- Tests cover the health/version handlers and `CI` remains green.

## Non-Goals
- ORIN deploy automation, GHCR publishing, or any endpoints that handle exports/PHI/PII.

## Test Plan
- Local: `python3 -m unittest discover -s tests -p 'test_*.py' -v`
- Local (optional): `docker build ...` and `docker compose up` (dev machine)

## Rollback Plan
- Revert the service/container additions.

