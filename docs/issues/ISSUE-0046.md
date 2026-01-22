# ISSUE-0046: CD: Establish version truth across artifacts (Python + iOS + container metadata)

GitHub: https://github.com/dave0875/HealthDelta/issues/46

## Objective
Make versioning deterministic and tag-driven so every published artifact is traceable to an exact `vX.Y.Z` tag and git SHA.

## Context / Why
Continuous Deployment requires auditable version truth:
- Python packaging is currently pinned to `0.0.0` (drift risk).
- iOS marketing/build versions are currently hard-coded in the project definition.
Without tag-driven versioning and accessible version reporting, deploy verification and rollback become error-prone.

## Acceptance Criteria
- Given a release tag `vX.Y.Z`, when the `Release` workflow runs, then the built wheel/sdist report version `X.Y.Z`.
- Given any environment where HealthDelta runs, when executing `healthdelta version`, then it prints a share-safe version string and (when available) a git SHA.
- Given a tag `vX.Y.Z`, when building iOS for distribution in CI (follow-on workflow), then marketing version is `X.Y.Z` and build number is deterministic and traceable to the CI run.
- CI proof: `.github/workflows/ci.yml` stays green on the implementing PR.
- Deployment proof: `.github/workflows/release.yml` on tag `vX.Y.Z` produces artifacts whose embedded version matches the tag.

## Non-Goals
- Backend containerization and ORIN deployment automation.
- Fastlane/TestFlight upload automation (handled in follow-on issues).

## Risks
- Risk: shallow clones prevent tag-based version resolution.
  - Mitigation: configure workflows to fetch tags where required for version computation.

## Test Plan
- Local: `python3 -m unittest discover -s tests -p 'test_*.py' -v`
- Local (optional): `python -m build` to verify wheel/sdist generation

## Rollback Plan
- Revert versioning changes and restore fixed versioning if needed.

