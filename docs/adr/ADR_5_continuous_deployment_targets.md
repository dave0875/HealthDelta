# ADR 5: Continuous deployment targets and proof of deployment

Status: Accepted

## Context
HealthDelta has multiple deliverables:
- A Python CLI (`healthdelta`) used for ingest, de-id, exports, DuckDB loading, and reporting.
- An iOS app used for incremental HealthKit collection and export.

Historically, “done” has been gated by CI green and uploaded CI artifacts (e.g., `ios-xcresult`). As the system becomes operational, we need explicit production targets and an auditable path to runnable artifacts.

## Decision
We define “production targets” and “deployment proof” per deliverable:

### 1) Python CLI production target
- **Target**: GitHub Releases (tagged versions), with share-safe build artifacts.
- **Proof**:
  - On every push to `main`, CI publishes a `cli-dist` Actions artifact containing `dist/*` from a PEP 517 build.
  - On version tags `vX.Y.Z`, CI creates/updates a GitHub Release and attaches `dist/*`.

### 2) iOS app production target
- **Target (future)**: TestFlight internal distribution (requires Apple credentials, signing, and App Store Connect configuration).
- **Current proof**:
  - macOS self-hosted runner executes `xcodebuild test` and uploads `ios-xcresult` on every push/PR (`.github/workflows/ci.yml`).
- **Blocked until configured**:
  - App signing identities/profiles and App Store Connect auth (API key / fastlane session) are not managed by this ADR; they require a dedicated issue with explicit credential handling and runner hardening.

### 3) Definition of done implications
- Issues must explicitly name:
  - which workflow/job proves correctness (CI)
  - which workflow/job/artifact proves deployment readiness (when the issue changes deployable artifacts)
- Docs-only issues may mark deployment proof as “N/A” but still require CI green.

## Consequences
- Maintainers can consistently reference “deployment proof” for CLI changes via the `Release` workflow and its published artifacts.
- iOS work remains rigorously validated through the authoritative self-hosted runner, while TestFlight/CD is deferred until credentials and signing are explicitly addressed.
- Governance becomes enforceable: “done” is measurable through workflow evidence rather than informal claims.

## Cross-references
- Issue #2: CI proof and macOS self-hosted runner artifacts
- Issue #41: Linux unit test artifacts
- Issue #43: this ADR + initial artifact deployment workflow
