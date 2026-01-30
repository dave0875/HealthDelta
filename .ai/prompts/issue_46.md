Issue: https://github.com/dave0875/HealthDelta/issues/46

Scope / intent (immutable)
- Establish version truth derived from git tags so published artifacts are traceable to an exact version and git SHA:
  - Python packaging version for wheel/sdist
  - `healthdelta version` CLI for share-safe reporting
  - iOS versioning strategy for CI/TestFlight builds (marketing version + build number)
  - container metadata requirements (OCI labels + `/version` output) specified for follow-on work

Acceptance criteria (restated)
- On tag `vX.Y.Z`, `Release` workflow produces Python dist with version `X.Y.Z`.
- `healthdelta version` prints a share-safe version string and (when available) a git SHA.
- iOS distribution builds on tag `vX.Y.Z` can set marketing version to `X.Y.Z` and a deterministic build number (implemented as scripts/helpers usable by future workflows).
- `CI` remains green; `Release` on tag is deployment proof for this change.

Constraints
- Deterministic, testable logic; follow TDD for non-trivial parsing/version logic.
- No secrets committed.

