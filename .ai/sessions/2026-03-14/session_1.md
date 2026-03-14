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

Outcome
- Added backend regression coverage for:
  - rejecting Ollama row-count-only responses
  - producing richer filtered `fitness` and `clinical` cards from mixed wellness/clinical datasets
- Updated `healthdelta/backend_server.py` so:
  - filtered insight facts extract source-specific active days, top wellness signals, and top clinical themes
  - filtered cards summarize those signals/themes instead of leading with row counts
  - Ollama outputs like `28,872 rows.` are rejected and replaced with deterministic fallback cards
- Verified locally with `TZ=UTC .venv/bin/python -m unittest tests.test_backend_insights_api -v`
- Pushed commit `fab3f1b`
- Verified GitHub runs:
  - CI `23080300431` passed
  - Release `23080300426` passed
- Built and deployed a live ORIN backend image `ghcr.io/dave0875/healthdelta-backend:issue247-live`
- Verified live `/insights/current?window_days=30` now returns meaningful summaries:
  - `Overview` references combined Apple Health activity plus structured clinical monitoring
  - `Fitness` references heart-rate-style telemetry, energy expenditure, step/activity counts, and percentage-based wellness signals
  - `Clinical` references oxygenation monitoring, blood counts and differentials, blood-bank/transfusion workflow, and serum chemistries
