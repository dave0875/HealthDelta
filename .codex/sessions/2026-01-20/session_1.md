# Session 1 — 2026-01-20

Issues worked
- #2 CI proof: Linux tests + self-hosted Xcode runner artifacts
- #3 Codex governance lock-in (prompt + execution discipline)

Execution environment
- Repository mutations executed on Ubuntu host: `GORF`
- Xcode execution performed only on self-hosted runner via GitHub Actions (no macOS repo mutation)

Work summary (Issue #2)
- Added `.codex/prompts/issue_2_followup_1.md` to capture post-hoc execution constraints without changing scope.
- Updated `ci.yml` to require runner labels `self-hosted`, `macOS`, `arm64`, `xcode`.
- Made simulator selection robust by selecting an available iPhone simulator via `simctl` (UDID destination).
- Fixed iOS project generation to pass Xcode build requirements by enabling Info.plist generation in `ios/HealthDelta/project.yml`.
- Ensured `.xcresult` and logs upload even when `xcodebuild` fails (artifact-based proof).
- Verified CI green and artifacts published.

Work summary (Issue #3)
- Documented binding Codex governance rules in `AGENTS.md`.
- Created immutable issue prompt file `.codex/prompts/issue_3.md`.

CI evidence
- CI (push/PR) green with artifacts: https://github.com/dave0875/HealthDelta/actions/runs/21160035185
  - Artifact `ios-xcresult` contains `HealthDelta.xcresult` and `xcodebuild.log`
- Device smoke (workflow_dispatch) successful: https://github.com/dave0875/HealthDelta/actions/runs/21160108632

