Issue: #227

Title: Package ORIN insights runtime dependencies in backend image

GitHub Issue URL: https://github.com/dave0875/HealthDelta/issues/227

Prompt
- Update the backend container image so it installs the runtime dependencies needed by the ORIN `/insights/current` analysis path.
- Prefer using the repository's declared Python dependencies rather than ad hoc host-side package installation.
- Add a release-image verification step that proves the built image can import the analysis modules required by the live insights path.
- Keep the change narrowly focused on reproducible backend runtime packaging.
