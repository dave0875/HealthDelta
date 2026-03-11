# Session 9

- Date: 2026-03-11
- Issue: #225
- Goal: Replace shallow ORIN iPhone insight generation with cards grounded in deterministic analytics artifacts derived from the uploaded iPhone dataset.

Actions
- Traced the current phone insight path and confirmed it uploads only the latest incremental iPhone run while `/insights/current` currently summarizes a small aggregate over `observations.ndjson`.
- Confirmed that richer deterministic analytics already exist in the repository via the iOS-direct DuckDB loader, report builder, and doctor's note generator.
- Scoped the implementation to materialize those artifacts inside the ORIN dataset directory and then derive fallback and Ollama-refined cards from that artifact set.
