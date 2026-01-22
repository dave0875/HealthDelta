Issue: https://github.com/dave0875/HealthDelta/issues/44

Scope / intent (immutable)
- Add a repo-first plan document (`docs/cd_plan.md`) describing the end-state Continuous Deployment design for:
  - backend deploy to ORIN (LAN)
  - iOS delivery to TestFlight
  - “150% verification” standards for both

Acceptance criteria (restated)
- `docs/cd_plan.md` exists and is share-safe (no secrets, no PII/PHI, no absolute local paths).
- `docs/cd_plan.md` references:
  - `docs/adr/ADR_5_continuous_deployment_targets.md`
  - `docs/runbook_cd.md`
- The plan is concrete enough to derive follow-on implementation issues (version truth, GHCR, ORIN deploy, Fastlane/TestFlight, verification harness).

Notes
- This issue does not implement workflows or deployment automation; it documents the end-state and required proofs.

