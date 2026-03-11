Issue: #226

Title: Roll ORIN backend to current main for insights API

GitHub Issue URL: https://github.com/dave0875/HealthDelta/issues/226

Prompt
- Restore the live ORIN backend on port 8080 so it runs the current `main` insights implementation rather than the stale `healthdelta-backend:issue223-test` image.
- Preserve the existing upload token, Ollama settings, and `/opt/healthdelta/data` bind mount during the rollout.
- Validate that `GET /insights/current` no longer returns the old missing-manifest error for the already-uploaded iPhone dataset.
- Keep the fix operationally minimal; do not redesign the deployment system as part of this issue.
