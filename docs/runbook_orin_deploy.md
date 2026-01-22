# Runbook: ORIN backend deployment (docker compose)

This runbook covers the ORIN-side prerequisites and operational commands for backend deployments.

## Deployment workflow
- Workflow: `.github/workflows/deploy_backend_orin.yml`
- Trigger: tag `vX.Y.Z` (or manual dispatch with `tag=vX.Y.Z`)
- Runner: ORIN self-hosted GitHub Actions runner (LAN-local)
- Deploy dir: `/opt/healthdelta`

## ORIN prerequisites
1) GitHub Actions self-hosted runner installed on ORIN
   - Labels must include: `self-hosted`, `linux`, `orin` (matches workflow `runs-on`)
2) Docker installed and runner user can run Docker
   - Runner user must be able to execute `docker` and `docker compose` without interactive prompts.
3) Tools required for verification
   - `curl`
   - `python3`
4) Deploy directory permissions
   - Preferred: allow the runner user to write `/opt/healthdelta`:
     - `sudo mkdir -p /opt/healthdelta`
     - `sudo chown <runner-user>:<runner-user> /opt/healthdelta`
   - The deploy workflow copies `deploy/orin/compose.yaml` and writes `/opt/healthdelta/.env` to pin the tag.

## What gets deployed
- Compose template: `deploy/orin/compose.yaml`
- Pinned tag file: `/opt/healthdelta/.env` with `HEALTHDELTA_BACKEND_IMAGE_TAG=vX.Y.Z`
- Service listens on `http://127.0.0.1:8080` (port mapping `8080:8080`)

## Verification (“150%” backend checks)
The deploy workflow verifies:
- Correct image tag is running (container image contains `:vX.Y.Z`)
- `GET /healthz` returns 200
- `GET /version` returns `version=X.Y.Z` and `git_sha=<sha>`
- Recent logs do not contain obvious fatal indicators (bounded tail scan)

## Rollback
1) Choose a previous tag (example: `v0.0.1`)
2) Update `/opt/healthdelta/.env`:
   - `HEALTHDELTA_BACKEND_IMAGE_TAG=v0.0.1`
3) Redeploy:
   - `cd /opt/healthdelta`
   - `docker compose --env-file .env pull backend`
   - `docker compose --env-file .env up -d --remove-orphans`
4) Verify:
   - `curl -fsS http://127.0.0.1:8080/healthz`
   - `curl -fsS http://127.0.0.1:8080/version`

## Credentials / secrets
- The workflow uses `GITHUB_TOKEN` for `docker login ghcr.io` with `packages: read` permission.
- If GHCR pulls fail on ORIN, use a fine-grained PAT with `read:packages` via a new secret and update the workflow accordingly (do not commit tokens).

