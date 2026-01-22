# ISSUE-0043: CD plan: define production targets + automate artifact deployments

GitHub: https://github.com/dave0875/HealthDelta/issues/43

## Objective
Define production targets and establish a CI-backed deployment/artifact publication path so “done” includes deploy proof.

## Context / Why
CI green is necessary but not sufficient for operational readiness. We need an auditable, automated path to runnable artifacts (at minimum for the Python CLI) and a documented plan for iOS distribution so each issue can point to concrete evidence of deployment readiness.

## Acceptance Criteria
- Given the repo, when reading the ADR/runbook, then maintainers can answer:
  - what “production” means for each artifact type
  - which workflow/job proves deploy readiness
  - what secrets/credentials are required and what is blocked
- Given a `main` push, when workflows run, then share-safe artifacts are published as Actions artifacts with deterministic naming.
- Given a version tag `vX.Y.Z`, when workflows run, then a GitHub Release is created/updated with attached CLI artifacts.
- Governance docs require issues to name deploy proof where applicable.
- CI is green before closing.

## Non-Goals
- Shipping real export data via CI or releases.
- App Store/TestFlight automation if credentials are not configured (document instead).

## Risks
- Risk: “Deployment” semantics become ambiguous between CLI and iOS.
  - Mitigation: Record explicit targets/evidence in ADR; require explicit proof in each issue’s acceptance criteria.

## Test Plan
- Local: `python3 -m unittest discover -s tests -p 'test_*.py' -v`
- CI: green run link + verify `cli-dist` artifact exists on `main` pushes; verify release creation on tag (manual).

## Rollback Plan
- Revert workflow/doc changes; no runtime behavior impacted.
