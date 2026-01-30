Issue: https://github.com/dave0875/HealthDelta/issues/56

Scope / intent (immutable)
- Fix tag-triggered Release builds so Python wheel/sdist versions match the tag exactly (`vX.Y.Z` → `X.Y.Z`).
- Keep CI green and re-verify by running Release on a new tag after the fix.

Acceptance criteria (restated)
- On tag `vX.Y.Z`, built dist version is exactly `X.Y.Z`.
- Release workflow’s tag version verification passes.
- Release workflow runs successfully on a new tag after the fix.

