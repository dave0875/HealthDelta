Issue: https://github.com/dave0875/HealthDelta/issues/43

Scope / intent (immutable)
- Define and document HealthDelta “production targets” and implement an initial continuous delivery/deployment workflow so “done” includes deploy proof (not only CI green).

Acceptance criteria (restated)
- Record an ADR under `docs/adr/` defining production targets (at minimum: Python CLI; iOS plan documented) and the workflow/job that proves deployment.
- Add a runbook describing deployment meaning, triggers, and required credentials/blockers.
- Implement a GitHub Actions workflow that:
  - on `main` pushes, builds share-safe artifacts and uploads them as Actions artifacts with deterministic naming
  - on tags (`vX.Y.Z`) or manual dispatch, creates a GitHub Release and attaches artifacts (at minimum: CLI dist)
- Update governance docs (AGENTS.md and/or issue template) so issues explicitly name deploy proof where applicable.
- Record audit artifacts (prompt/session/review/TIME.csv) and close with green CI.

Plan
1) Add `docs/adr/ADR_5_continuous_deployment_targets.md`:
   - define what “production” means for CLI vs iOS at this stage
   - define deploy evidence (which workflow/job/artifact)
   - document what is blocked until credentials exist (TestFlight)
2) Add `docs/runbook_cd.md`:
   - how to trigger/tag releases
   - where to fetch artifacts
   - security/privacy constraints (no exports; share-safe only)
3) Add `.github/workflows/release.yml`:
   - build CLI dist on `main` and upload `cli-dist` artifact
   - on tags, publish GitHub Release with attached dist assets
4) Update `AGENTS.md` and `.github/ISSUE_TEMPLATE/story.md` to require explicit deploy proof when a story affects deployable artifacts.
5) Verify local tests; verify CI green + artifacts; comment and close.

Constraints
- No PHI/PII in artifacts or logs; no real exports uploaded.
- Self-hosted macOS runner remains authoritative for Xcode/iOS CI; production iOS deployment may be blocked until Apple credentials are configured.
