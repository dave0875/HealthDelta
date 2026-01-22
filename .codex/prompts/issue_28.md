Issue: https://github.com/dave0875/HealthDelta/issues/28

Scope / intent (immutable)
- Extend identity build outputs with an explicit PersonLink registry and verification state.
- Implement initial linking rules: name match produces an `unverified` link only when unambiguous; ambiguous cases avoid auto-merge.
- Preserve existing outputs (`people.json`, `aliases.json`) for current pipeline compatibility.

Acceptance criteria (restated)
- Identity build produces a PersonLink registry file containing:
  - `system_fingerprint`
  - `source_patient_id`
  - `person_key`
  - `verification_state` (`verified` | `unverified` | `user_confirmed`)
- Initial rules:
  - exact first+last match creates an unverified link when unambiguous
  - ambiguity creates a new `person_key` (no auto-merge)
- Unit tests:
  - exact match → unverified link
  - ambiguity → distinct `person_key`
- Update `docs/runbook_identity.md` describing the new output.
- CI green required before closing; add audit artifacts (session log, review, TIME.csv).

Implementation plan
1) Add `data/identity/person_links.json` output:
   - format: `{"schema_version":1,"links":[...]}` with stable JSON formatting.
   - derive `system_fingerprint` and `source_patient_id` as sha256 fingerprints (no raw identifiers).
2) Update identity build:
   - load existing person links into a `(system_fingerprint, source_patient_id) -> person_key` map.
   - do a pre-pass over current run’s Patient resources to count name collisions within the run.
   - when no existing link exists:
     - if name is unique within the run and maps to exactly one existing person_key, link to it with `verification_state="unverified"`
     - otherwise create a new `person_key` (no merge)
3) Tests use synthetic FHIR Patient resources only and assert:
   - unambiguous run produces `verification_state="unverified"` link
   - ambiguous run produces multiple person_keys for the same name and links map accordingly
4) Update runbook_identity.md to document `person_links.json` and its privacy properties.

Determinism and privacy notes
- PersonLink identifiers are fingerprints (sha256), not raw IDs.
- Output ordering is deterministic (sorted where feasible); no absolute paths in outputs.
- Identity outputs remain local-only; share bundles continue to exclude identity.

Execution constraints
- All repository mutations executed only on Ubuntu host `GORF`.
- GitHub interactions via `gh` CLI only.
