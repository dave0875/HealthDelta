# ADR_1 — Self-Hosted Xcode Runner Is Authoritative

Issue: https://github.com/dave0875/HealthDelta/issues/2
Date: 2026-01-19

## Context
HealthDelta requires auditable, objective proof of correctness. iOS builds and tests depend on macOS/Xcode and are sensitive to toolchain versions, simulator runtimes, signing state, and device entitlements.

GitHub-hosted macOS runners can change over time and do not reflect the project’s “real” Xcode environment. For HealthKit- and entitlement-related workflows, we need a stable, owned environment.

## Decision
- Use the MacBook Pro as a self-hosted GitHub Actions runner for all Xcode-related CI work.
- Require runner labels: `self-hosted`, `macOS`, `xcode`.
- Require `ci.yml` to run `xcodebuild test` on the self-hosted runner and upload the full `.xcresult` bundle as an artifact.

## Alternatives Considered
- **GitHub-hosted `macos-latest`**: simpler setup but less control over Xcode versions/runtimes and less aligned with “authoritative” environment requirements.
- **Separate CI system (e.g., Jenkins/Buildkite)**: more moving parts and less integrated with GitHub issue/PR traceability.

## Consequences
- CI correctness proof includes immutable artifacts (logs + `.xcresult`) generated on the authoritative environment.
- The repo must maintain a runbook for installing/updating Xcode and keeping the runner online.
- PRs may block if the self-hosted runner is offline; operational reliability becomes part of engineering discipline.

