Issue: https://github.com/dave0875/HealthDelta/issues/54

Scope / intent (immutable)
- Build and publish the backend container image to GHCR on `v*` tags.
- Embed version truth into the image (build args + OCI labels).
- Verify the pushed image by pulling and running it in CI and checking `/healthz` and `/version`.

Acceptance criteria (restated)
- Tag `vX.Y.Z` publishes `ghcr.io/<owner>/healthdelta-backend:vX.Y.Z` and `:latest`.
- `/version` reports the expected `version=X.Y.Z` and `git_sha=<sha>` for the tag.
- OCI labels include `org.opencontainers.image.version` and `org.opencontainers.image.revision`.
- Workflow logs/artifacts include image digest(s) and verification output.

