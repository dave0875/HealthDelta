# Runbook: Continuous deployment / artifact publication

This runbook defines how HealthDelta produces share-safe build artifacts and what evidence constitutes “deployment proof”.

## Workflows

### CI (tests)
- Workflow: `.github/workflows/ci.yml`
- Proof:
  - Linux job passes (non-iOS tests).
  - macOS job passes and uploads `ios-xcresult`.

### Release (artifact publication)
- Workflow: `.github/workflows/release.yml`
- On every push to `main`:
  - Publishes `cli-dist` as a GitHub Actions artifact containing `dist/*` (Python wheel + sdist).
- On tags `vX.Y.Z` (and manual dispatch):
  - Creates/updates a GitHub Release and attaches the CLI `dist/*` artifacts.

## Operator guidance (share-safety)
- Never upload real Apple Health exports (or staged copies) to GitHub Actions artifacts or Releases.
- Only share-safe derived artifacts may be published (code builds, logs, synthetic test fixtures, CI reports).

## How to cut a CLI release
1) Decide the version and ensure `main` is ready to tag (must be tracked by an issue).
2) Create an annotated tag `vX.Y.Z` on `main`.
3) Push the tag to GitHub.
4) Confirm the `Release` workflow run is green and the GitHub Release has the expected assets attached.

Note: CLI packaging version is tag-derived; do not manually edit a fixed `version = ...` field in `pyproject.toml`.

## iOS distribution (current state)
- TestFlight / App Store distribution is not configured by default.
- Current authoritative proof for iOS is the macOS self-hosted CI runner (`ios-xcresult` artifact).
- Planned: distribution builds will set `MARKETING_VERSION` from the git tag and `CURRENT_PROJECT_VERSION` from the CI run number (helper: `scripts/cd/derive_ios_versions.py`).

## References
- Production targets ADR: `docs/adr/ADR_5_continuous_deployment_targets.md`
