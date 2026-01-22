# ISSUE-0044: CD: End-to-end continuous deployment plan (backend + TestFlight)

GitHub: https://github.com/dave0875/HealthDelta/issues/44

## Objective
Create a share-safe, repo-first CD plan document describing the end-state automation across GitHub Actions, ORIN, GORF, and macOS for backend deployment and iOS TestFlight delivery.

## Context / Why
HealthDelta currently has CI proof and a release workflow for share-safe CLI artifacts. To extend to true Continuous Deployment (backend deploys and TestFlight uploads) safely, we need a single plan that defines triggers, version truth, verification standards, and intended workflow boundaries so implementation proceeds as small, auditable issues.

## Acceptance Criteria
- `docs/cd_plan.md` exists and is share-safe (no secrets, no PII/PHI, no absolute local paths).
- `docs/cd_plan.md` documents:
  - environments (GitHub / ORIN / GORF / macOS)
  - intended triggers and workflows
  - “150% verification” checks for backend deploys and TestFlight uploads
- `docs/cd_plan.md` references `docs/adr/ADR_5_continuous_deployment_targets.md` and `docs/runbook_cd.md`.

## Non-Goals
- Implementing Dockerfiles, compose configs, deploy workflows, Fastlane, or TestFlight automation.
- Changing existing CI or release behavior.

## Risks
- Risk: Plan becomes stale or overly aspirational.
  - Mitigation: Keep it tied to concrete follow-on issues and objective verification checks.

## Test Plan
- N/A (documentation-only change).

## Rollback Plan
- Revert documentation changes.

