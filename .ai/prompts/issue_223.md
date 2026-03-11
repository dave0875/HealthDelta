Issue: #223

Title: Refine ORIN iPhone insight cards with local Ollama analysis

GitHub Issue URL: https://github.com/dave0875/HealthDelta/issues/223

Prompt
- Upgrade `GET /insights/current` so ORIN can return more useful, share-safe iPhone insight cards using its local Ollama runtime.
- Preserve the current heuristic path as a fallback when Ollama is unavailable, misconfigured, or returns invalid output.
- Keep the iPhone fetch contract stable; the app should not need a new transport or UI redesign.
- Update tests and ORIN deployment/runbook docs to cover the Ollama-backed path.
