# Issue 29 — Identity workflow: CLI review/confirm for unverified PersonLinks

GitHub: https://github.com/dave0875/HealthDelta/issues/29

## Objective
Provide a non-UI, deterministic CLI workflow to review unverified identity links and record human confirmation, so ambiguous identities are never silently auto-merged.

## Context
Issue #28 introduces `person_links.json` with `verification_state`. We need an immediate safety valve to review and confirm links without building UI yet.

## Acceptance Criteria (from GitHub issue)
- Add `healthdelta identity review` listing unverified PersonLinks with minimal share-safe hints.
- Add `healthdelta identity confirm --link <id>` (or equivalent) marking a link as `user_confirmed` deterministically.
- Tests prove deterministic ordering and deterministic updates; no PII printed.
- Update `docs/runbook_identity.md`.
- CI green required before closing.

## Non-goals
- iOS UI.
- Auto-merging identities.
- Any network activity.

## Risks
- Printing identifiers that might be considered sensitive; mitigate by using link IDs derived from existing fingerprints and avoiding names/DOBs.
- Non-deterministic updates (timestamps); mitigate by not writing timestamps for confirmations in this slice.

## Test Plan
- Synthetic identity directory with a `person_links.json` containing multiple links:
  - `identity review` prints only unverified links sorted deterministically.
  - `identity confirm` updates exactly one link state to `user_confirmed` and is idempotent.
  - output does not contain synthetic banned tokens.

## Rollback Plan
- Revert commits referencing Issue #29.
- Use manual JSON editing for confirmation (not recommended).

