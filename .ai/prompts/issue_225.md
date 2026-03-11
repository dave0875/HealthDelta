Issue: #225

Title: Drive ORIN iPhone insights from deterministic analytics artifacts

GitHub Issue URL: https://github.com/dave0875/HealthDelta/issues/225

Prompt
- Upgrade `GET /insights/current` so ORIN generates or reuses deterministic analytics artifacts for the current uploaded iPhone dataset before returning phone-facing cards.
- Reuse the existing iOS-compatible DuckDB, reporting, and doctor's note pipeline instead of deriving cards only from raw upload row-count aggregates.
- Keep the iPhone transport and card contract stable.
- When Ollama is configured, use it to refine artifact-grounded facts rather than to infer structure from only raw observation aggregates.
- When Ollama is unavailable or unusable, fall back to deterministic artifact-grounded cards without failing the endpoint.
- Add tests and docs for the new ORIN insight generation path.
