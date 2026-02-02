# Session 16 - 2026-02-01

Issue: #134

Goal
- Publish backend release images as native multi-arch manifests (`linux/amd64`, `linux/arm64`).

Notes
- Updated `.github/workflows/release.yml` to set up QEMU and build/push a multi-arch backend image.
- Added manifest verification step using `docker buildx imagetools inspect` and architecture assertions.
- Updated `docs/runbook_cd.md` to document multi-arch backend publication behavior.

Local verification
- GitHub Actions workflow validation on PR
