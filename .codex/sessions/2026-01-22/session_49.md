# Session 49 — 2026-01-22

Issues worked
- #54 CD: Build and push backend image to GHCR on tag

Execution environment
- Repository mutations executed on Ubuntu host: `GORF`

Work summary
- Extended `Release` workflow to build/push backend image to GHCR on `v*` tags.
- Embed version truth in the image via build args (`HEALTHDELTA_VERSION`, `HEALTHDELTA_GIT_SHA`) and OCI labels.
- Added CI verification that pulls the pushed image and checks `/healthz` + `/version`.

Local verification
- N/A (tag-triggered workflow verification)
