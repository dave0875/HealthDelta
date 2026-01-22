Issue: https://github.com/dave0875/HealthDelta/issues/60

Scope / intent (immutable)
- Add tag-triggered backend deployment automation for ORIN using docker compose:
  - pin image tag in `/opt/healthdelta` deployment directory
  - `docker compose up -d` deploy
  - post-deploy “150% verification” using `/healthz`, `/version`, and basic log scan
- Document ORIN runner prerequisites, GHCR pull auth, and rollback steps.

Acceptance criteria (restated)
- On tag `vX.Y.Z`, deploy workflow runs on ORIN self-hosted runner and deploys pinned `ghcr.io/<owner>/healthdelta-backend:vX.Y.Z`.
- Verification proves image tag, `/version` values, `/healthz` success, and no obvious fatal logs.
- Rollback guidance exists; no secrets committed.

