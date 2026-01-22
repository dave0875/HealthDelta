# ISSUE-0060: CD: ORIN deploy workflow (docker compose) + post-deploy verification

GitHub: https://github.com/dave0875/HealthDelta/issues/60

## Objective
Deploy the backend to ORIN automatically on tags using docker compose, with strong post-deploy verification and clear rollback guidance.

## Context / Why
Backend images are published to GHCR on tags and include `/healthz` and `/version`. ORIN deploy automation completes backend CD by pulling a pinned image tag on a LAN-local runner and validating the running version matches the tag.

## Acceptance Criteria
- On tag `vX.Y.Z`, deploy workflow runs on ORIN self-hosted runner and deploys `ghcr.io/<owner>/healthdelta-backend:vX.Y.Z` via docker compose in `/opt/healthdelta`.
- Post-deploy verification proves:
  - expected image tag is running
  - `/version` reports `version=X.Y.Z` and `git_sha=<sha>`
  - `/healthz` returns HTTP 200
  - bounded log scan shows no obvious fatal errors
- Rollback guidance exists (pin previous tag and redeploy).
- No secrets committed; CI remains green.

## Test Plan
- CI: workflow files lint by Action runner; PR CI green.
- ORIN: execute tag deploy once runner + secrets are configured (deployment proof).

## Rollback Plan
- Re-deploy previous tag by updating pinned tag and running compose up.

