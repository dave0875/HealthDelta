# ISSUE-0056: Release: fix tag builds to produce exact PEP 440 version (no .post/.dev)

GitHub: https://github.com/dave0875/HealthDelta/issues/56

## Objective
Ensure tag-triggered Release builds embed the exact tag version into Python artifacts so version truth checks are deterministic.

## Context / Why
Tag `v0.0.1` produced `healthdelta-0.0.1.post1.dev0`, which caused the Release workflow’s tag version verification step to fail and blocks end-to-end release proof.

## Acceptance Criteria
- On tag `vX.Y.Z`, `python -m build` produces wheel/sdist with version exactly `X.Y.Z`.
- Release workflow’s tag version verification step passes.
- Deployment proof: Release workflow succeeds on a new tag after the fix.
- CI remains green.

## Non-Goals
- Changing backend publishing behavior beyond aligning version truth.

## Test Plan
- CI: `CI` workflow green on PR.
- Release proof: push a new tag after merge and confirm Release workflow is green.

