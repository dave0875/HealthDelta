Issue: #247
Date: 2026-03-14

Summary
- Investigated live ORIN `/insights/current` output after user reported the iPhone app remained useless.
- Confirmed the backend was returning degenerate cards such as `28,872 rows.` and `1,213 rows.` for fitness and clinical domains.
- Traced the problem to the ORIN insight-generation path in `healthdelta/backend_server.py`, specifically the combination of permissive Ollama refinement acceptance and fallback summaries that still center row counts too heavily.

Evidence
- Live `/insights/current?window_days=30` returned:
  - `Fitness` -> `28,872 rows.`
  - `Clinical` -> `1,213 rows.`
  - `Overview` with mixed row-count-heavy summary text.
- Current dataset still contains richer context than those cards expose.

Planned fix
- Strengthen deterministic fallback cards so they lead with meaningful health/fitness/clinical scope and signals.
- Reject low-information Ollama output before returning it to the iPhone app.
- Add regression tests for row-count-only Ollama responses and richer fallback behavior.
