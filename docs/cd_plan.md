# Continuous Deployment Plan (end-state)

This document is the repo-first implementation plan for end-to-end Continuous Deployment (CD) across:
- GitHub (Actions, Releases, GHCR)
- ORIN (LAN host; runs containers; self-hosted runner)
- GORF (Linux dev box; local build/test convenience)
- macOS host (Xcode/iOS builds; may host runner if needed)

This plan extends the current “artifact publication” baseline defined in:
- Targets + deployment proof: `docs/adr/ADR_5_continuous_deployment_targets.md`
- Operator runbook: `docs/runbook_cd.md`

## Current baseline (already implemented)
- CI: `.github/workflows/ci.yml` (Linux unittest + macOS Xcode tests)
- Release: `.github/workflows/release.yml` (build Python wheel/sdist; create GitHub Release on `v*` tags)

## End-state diagram (conceptual)

```
               ┌──────────────────────────────────────────────┐
               │                    GitHub                     │
               │  Actions: CI / Release / Deploy / TestFlight  │
               │  Releases: source-of-truth tags `vX.Y.Z`      │
               │  GHCR: backend images                         │
               └───────────────┬───────────────────────────────┘
                               │ tag `vX.Y.Z`
                   ┌───────────┴───────────┐
                   │                       │
                   │                       │
        ┌──────────▼──────────┐  ┌────────▼─────────┐
        │ ORIN (LAN)           │  │ macOS runner       │
        │ self-hosted runner   │  │ (prefer GH-hosted  │
        │ pulls GHCR image     │  │ macOS if possible) │
        │ docker compose up    │  │ fastlane upload    │
        │ post-deploy verify   │  │ post-upload verify │
        └──────────────────────┘  └───────────────────┘
```

## Triggers (source of truth)
- Git tag `vX.Y.Z` is the single “release intent” event.
- GitHub Release creation is derived from the tag (not an independent source of truth).

## Version truth (shared invariant)
For any deployable artifact built from tag `vX.Y.Z`:
- The artifact must report `version = X.Y.Z` and the exact `git_sha` used to build it.
- CI/CD must record build metadata (workflow run id, timestamp, and provenance) as artifacts.

Planned mechanisms:
- Python (CLI): version from tag (no manual editing drift).
- Backend container (GHCR): OCI labels embed `version`, `git_sha`, `build_time`, `source`.
- Backend runtime: `/version` returns `version`, `git_sha`, and build metadata.
- iOS (TestFlight): marketing version from tag; build number deterministic from CI run; metadata archived.

## Workflows (target)

### 1) CI (fast checks)
Workflow: `.github/workflows/ci.yml`
- Linux: unit tests (share-safe artifacts only)
- iOS: simulator tests (runner chosen per Xcode/network constraints)

### 2) Release (publish artifacts on tag)
Workflow: `.github/workflows/release.yml` (existing baseline; extend later)
- Build + publish Python dist
- Build + push backend image to GHCR (tagged `vX.Y.Z` and `latest`)
- Generate a deploy report artifact summarizing versions + proofs

### 3) Deploy backend (ORIN)
Workflow: planned `.github/workflows/deploy_backend.yml`
Runs on: ORIN self-hosted runner (LAN locality requirement)
Steps:
- Pull `ghcr.io/<owner>/healthdelta-backend:vX.Y.Z`
- Update `/opt/healthdelta/compose.yaml` (pinned tag)
- `docker compose up -d` with safe rollout
- Run post-deploy verification harness (see “150% verification”)
- Upload deploy report artifact (logs + results)

### 4) TestFlight (iOS)
Workflow: planned `.github/workflows/ios_testflight.yml`
Runs on: GitHub-hosted macOS runner (preferred), or a dedicated macOS self-hosted runner if required.
Steps:
- Run simulator tests for the tagged commit
- Build + sign using Fastlane (App Store Connect API key auth)
- Upload to TestFlight
- Verify build exists and version/build metadata match expectations
- Upload IPA + dSYM + build metadata as artifacts

## “150% verification” (required checks)

### Backend deploy verification (ORIN)
Must prove:
1) Correct image tag is running (compose service image == `...:vX.Y.Z`)
2) Runtime reports expected `version` and `git_sha` (via `/version`)
3) Health check passes (`/healthz` or equivalent smoke command)
4) Rollout behavior is safe (no downtime or bounded downtime; restart policy sane)
5) Logs contain no obvious fatal errors post-deploy (bounded tail scan)

### iOS/TestFlight verification
Must prove:
1) Marketing version aligns with tag (`X.Y.Z`)
2) Build number deterministic and traceable to CI run
3) Upload succeeded and the build is visible in TestFlight/App Store Connect
4) Simulator tests pass for the tagged commit
5) IPA + dSYM + metadata are archived as CI artifacts (and optionally attached to the GitHub Release)

## Safety and reliability “goodies” (preferred defaults)
- GitHub Environments for production deploys (optional approvals)
- Concurrency controls on deploy workflows (avoid tag collision)
- Dependency caching (pip, bundler) for speed and consistency
- Provenance metadata recorded in deploy report (git sha, run id, timestamps)
- Explicit rollback instructions (pin previous tag; redeploy)

## Secrets / credentials (do not commit)
- GHCR pull on ORIN: token for `docker login ghcr.io` (fine-grained PAT recommended)
- App Store Connect: API key id/issuer id + `p8` (base64) for Fastlane
- Code signing (if using match): `MATCH_PASSWORD` + signing repo access

## Implementation breakdown (issues to create)
- Establish version truth across Python/iOS/backend runtime
- Backend containerization + `/healthz` and `/version`
- GHCR build/push on tag with OCI labels
- ORIN deploy automation + post-deploy verification harness
- Fastlane scaffolding for TestFlight + deterministic build metadata
- iOS TestFlight workflow + post-upload verification
- Unified deploy report artifacts (backend + iOS)

