# Session 7

- Date: 2026-03-11
- Issue: #223
- Goal: Tighten the live Ollama prompt so ORIN returns stable refined cards instead of intermittently falling back to heuristic output.

Actions
- Observed that the first live production prompt sometimes fell back to heuristic cards even though the ORIN proxy and CPU-mode model path were healthy.
- Simplified the Ollama prompt to a fixed two-card JSON contract with exact titles `Interpretation` and `Confidence`.
- Rebuilt the ORIN side-port backend container and confirmed the live model returned stable `sourceLabel=orin/ollama` cards with the tightened prompt.
- Prepared promotion of that exact build to the live `:8080` backend service.
