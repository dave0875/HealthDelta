# Codex Audit Trail

`.codex/` is the authoritative audit trail for Codex-driven work in this repository.

## Structure
- `prompts/`: substantial instructions and refinements (must reference GitHub issues)
- `sessions/`: per-session logs (date-based folders)
- `decisions/`: ADRs for architectural/process decisions

## Rules
- Do not store secrets (tokens, `.env`, credentials) in `.codex/`.
- Prefer append-only updates; don’t rewrite history unless correcting factual errors.

