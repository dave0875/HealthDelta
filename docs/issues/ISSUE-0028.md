# Issue 28 — Identity model: introduce PersonLink registry + verification_state

GitHub: https://github.com/dave0875/HealthDelta/issues/28

## Objective
Extend identity build outputs with an explicit PersonLink registry capturing `(system_fingerprint, source_patient_id) -> person_key` and an explicit `verification_state`, so identity resolution is auditable and avoids unsafe auto-merges.

## Context
Current identity build outputs are name-based and do not explicitly model links between external identifiers and canonical people. The project requires a canonical PersonLink model with verification state.

## Acceptance Criteria (from GitHub issue)
- Add a PersonLink registry output containing:
  - `system_fingerprint`
  - `source_patient_id`
  - `person_key`
  - `verification_state` (`verified` | `unverified` | `user_confirmed`)
- Implement initial linking rules:
  - exact first+last match creates an unverified link when unambiguous
  - ambiguity creates a new `person_key` (no auto-merge)
- Tests cover exact match and ambiguity behavior.
- Update `docs/runbook_identity.md`.
- CI green required before closing.

## Non-goals
- UI for human confirmation.
- De-identification changes.
- Reworking downstream export logic to use PersonLink (future issue).

## Risks
- Ambiguity heuristics could impact operator stability across runs if too strict.
- Fingerprinting strategy must avoid leaking raw external identifiers.

## Test Plan
- Synthetic-only identity build tests asserting:
  - `person_links.json` is produced and includes `verification_state="unverified"` for unambiguous link creation.
  - ambiguous same-name patients in a single run result in distinct `person_key` values.

## Rollback Plan
- Revert commits referencing Issue #28.
- Continue using name-based identity without PersonLinks (less auditable).

