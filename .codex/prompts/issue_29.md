Issue: https://github.com/dave0875/HealthDelta/issues/29

Scope / intent (immutable)
- Add a CLI safety valve to review and confirm unverified PersonLinks produced by Issue #28.
- Ensure no PII is printed, output ordering is deterministic, and state updates are deterministic and local-only.

Acceptance criteria (restated)
- Add `healthdelta identity review` listing unverified PersonLinks with minimal share-safe hints.
- Add `healthdelta identity confirm --link <id>` (or equivalent) updating `verification_state` to `user_confirmed` deterministically.
- Tests prove:
  - review output ordering is deterministic
  - confirm updates state deterministically and is idempotent
  - no PII printed
- Update `docs/runbook_identity.md` with review/confirm workflow.
- CI green required before closing; add audit artifacts (session log, review, TIME.csv).

Design choices
- Link identifier for CLI (`--link`) is computed, not stored:
  - `link_id = sha256(system_fingerprint + ':' + source_patient_id)`
  - This yields a stable 64-hex identifier without exposing raw IDs.
- Commands operate on local identity directory (default `data/identity`) and never touch network.

Plan
1) Add helper functions in `healthdelta/identity.py`:
   - list unverified links (sorted by `link_id`)
   - confirm a link by `link_id` (update JSON deterministically; idempotent)
2) Wire CLI in `healthdelta/cli.py` under `healthdelta identity`:
   - `review [--identity <dir>]`
   - `confirm --link <link_id> [--identity <dir>]`
3) Add synthetic tests via subprocess:
   - `identity review` output stable + contains no banned tokens
   - `identity confirm` updates `person_links.json` deterministically and rerun is a no-op
4) Update `docs/runbook_identity.md` to document the workflow and that output is share-safe.

Execution constraints
- All repository mutations executed only on Ubuntu host `GORF`.
- GitHub interactions via `gh` CLI only.
