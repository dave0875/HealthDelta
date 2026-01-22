# ISSUE-0054: CD: Build and push backend image to GHCR on tag

GitHub: https://github.com/dave0875/HealthDelta/issues/54

## Objective
Publish a verifiable backend container image to GHCR on release tags so ORIN deployments can pull a pinned image and validate version truth.

## Context / Why
With a minimal backend service and Dockerfile in place, CD requires a reproducible publishing pipeline that embeds version truth and performs post-build verification, producing observable proof (digests + logs).

## Acceptance Criteria
- On tag `vX.Y.Z`, workflow pushes `ghcr.io/<owner>/healthdelta-backend:vX.Y.Z` and `:latest`.
- Image build embeds `HEALTHDELTA_VERSION=X.Y.Z` and `HEALTHDELTA_GIT_SHA=<sha>` so `/version` reports expected values.
- Workflow pulls and runs the pushed image and verifies `/healthz` + `/version`.
- Image includes OCI labels for `org.opencontainers.image.version` and `org.opencontainers.image.revision`.
- Workflow logs show image digest(s) and verification output.

## Non-Goals
- ORIN deployment automation and compose pinning.

## Test Plan
- CI: run on tag in GitHub Actions and confirm GHCR publish + verification logs.

## Rollback Plan
- Revert workflow changes; stop publishing backend images.

