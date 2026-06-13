# Session 1 - Issue #258

Date: 2026-06-13
Issue: #258 - Ops: realign mail server HealthDelta deployment to latest release tag

Goals
- Confirm whether a release-style HealthDelta tag already exists.
- Replace the ad hoc `issue247-live` deployment on `mail.fitness-pals.com` with the latest release-style tag.
- Verify the live runtime remains healthy and reports release metadata.

Progress
- Opened Issue #258 with the required template.
- Confirmed the repository already has release-style tags and GitHub Releases through `v0.0.10`.
- Confirmed `mail.fitness-pals.com` was pinned to `HEALTHDELTA_BACKEND_IMAGE_TAG=issue247-live` in `/opt/healthdelta/.env`.
- Backed up the remote env file and changed only `HEALTHDELTA_BACKEND_IMAGE_TAG` to `v0.0.10`, preserving upload token, bind host, and Ollama settings.
- Pulled `ghcr.io/dave0875/healthdelta-backend:v0.0.10` and recreated the backend container with `docker compose`.
- Observed one transient `curl` connection reset immediately after container restart, then verified steady-state health.

Verification
- GitHub Release: `v0.0.10` published at `2026-03-13T21:32:01Z`
- Release tag commit: `3734a1147b441e7ebd39ffcfc326e05574504604`
- Remote container image: `ghcr.io/dave0875/healthdelta-backend:v0.0.10`
- Remote health: `GET http://127.0.0.1:8080/healthz` -> `{"ok": true}`
- Remote version: `GET http://127.0.0.1:8080/version` -> `{"git_sha": "3734a1147b441e7ebd39ffcfc326e05574504604", "version": "0.0.10"}`
- Remote env now pins `HEALTHDELTA_BACKEND_IMAGE_TAG=v0.0.10`

Residual note
- Issue #258 remains open in GitHub until the local audit-artifact changes are committed/pushed and the operator decides whether to close it immediately or after any additional deployment-proof bookkeeping.
