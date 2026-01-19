# Session 2 — 2026-01-19

Issues worked
- #2 CI proof: Linux tests + self-hosted Xcode runner artifacts

Work summary
- Created Issue #2 and recorded the CI constraints prompt in `.codex/prompts/issue_2.md`.
- Added ADR documenting the decision to treat the self-hosted MacBook Pro runner as authoritative for Xcode work.
- Implemented GitHub Actions workflows:
  - `CI` (`.github/workflows/ci.yml`) for push + PR (Linux tests + macOS self-hosted Xcode simulator tests with `.xcresult` artifacts).
  - `Device Smoke (manual)` (`.github/workflows/device_smoke.yml`) for workflow_dispatch device-oriented build checks.
- Added `docs/runbook_xcode.md` and referenced it from `AGENTS.md`.
- Added minimal iOS project definition via `xcodegen` (`ios/HealthDelta/project.yml`) and minimal Swift sources/tests to enable `xcodebuild test` in CI.
- Added a minimal Linux unittest (`tests/test_ci_sanity.py`) to prove headless test execution wiring.

CI evidence
- CI run (push on `main`): https://github.com/dave0875/HealthDelta/actions/runs/21147697604
  - Linux job: passed
  - macOS self-hosted job: queued (waiting for runner availability)

Follow-ups
- Ensure the MacBook Pro runner is online with labels `self-hosted`, `macOS`, `xcode`, then re-run `CI` to capture `.xcresult` artifact proof.

