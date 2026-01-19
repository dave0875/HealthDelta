# Xcode + Self-Hosted Runner Runbook

This project uses a MacBook Pro as the authoritative environment for all Xcode-related CI work.

## Self-hosted GitHub Actions runner (MacBook Pro)

Required runner labels:
- `self-hosted`
- `macOS`
- `xcode`

Runner setup overview:
1) On GitHub, navigate to `Settings → Actions → Runners → New self-hosted runner`.
2) Select `macOS`, then follow the provided install steps on the MacBook Pro.
3) Configure the runner to run as a persistent service (recommended).
4) Ensure the runner is online before expecting PR CI to pass.

## Required Xcode version and simulator runtimes

The self-hosted runner must have:
- Xcode installed (version pinned by team decision; record future changes via ADR).
- iPhone Simulator runtimes that include the device model used by CI.

Current CI default destination (override via env var `DESTINATION`):
- `platform=iOS Simulator,name=iPhone 15`

Verify locally on the runner:
- `xcodebuild -version`
- `xcrun simctl list devices available`

## Workflows

### `ci.yml` (push + PR)

Jobs:
- `Linux (non-iOS tests)` on `ubuntu-latest`
  - Runs: `python3 -m unittest discover -s tests -p 'test_*.py' -v`
- `macOS (Xcode simulator tests)` on `[self-hosted, macOS, xcode]`
  - Generates `ios/HealthDelta/HealthDelta.xcodeproj` via `xcodegen` before testing
  - Runs: `xcodebuild test` and uploads:
    - `artifacts/HealthDelta.xcresult`
    - `artifacts/xcodebuild.log`
    - `artifacts/junit.xml` (only if `xcpretty` is available)

Xcode project generation:
- This repo uses `xcodegen` with `ios/HealthDelta/project.yml` to generate the Xcode project in CI.
- Ensure `xcodegen` is installed on the self-hosted runner (Homebrew is acceptable).

JUnit note:
- If you want JUnit published for GitHub UI counts, install `xcpretty` on the runner.
- Recommended: `sudo gem install xcpretty` (or `gem install --user-install xcpretty` and ensure it’s on `PATH`).

### `device_smoke.yml` (manual)

Purpose:
- Entitlement/signing/HealthKit permission sanity and “does it run” checks on a physically connected iPhone.

Trigger:
- GitHub Actions → `Device Smoke (manual)` → `Run workflow`

Notes:
- This workflow only builds by default; installing/running on a specific device requires signing and may require additional inputs (UDID/team provisioning). Capture future changes in an issue + ADR.

## Re-running workflows

From GitHub UI:
- Open the workflow run → `Re-run all jobs`

From CLI:
- `gh workflow run CI -R dave0875/HealthDelta`
- `gh run list -R dave0875/HealthDelta`
- `gh run watch -R dave0875/HealthDelta <run-id>`
