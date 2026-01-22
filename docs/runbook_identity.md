# Identity Runbook (Bootstrap Person Registry)

## Goal
Build a canonical person registry and observed alias/provenance records from staged data, using an explicit, testable name parsing + matching rule.

## Command
From the repo root:

- `healthdelta identity build --input data/staging/<run_id>`
- `healthdelta identity review [--identity data/identity]`
- `healthdelta identity confirm --link <link_id> [--identity data/identity]`

## Inputs
The `--input` path must be a staging run directory produced by `healthdelta ingest` (Issue #4), and must include `layout.json`.

## Outputs
Writes:
- `data/identity/people.json`
- `data/identity/aliases.json`
- `data/identity/person_links.json`

Notes:
- Identity outputs are **local-only** and are excluded from share bundles by design.
- `person_links.json` stores only sha256 fingerprints for external identifiers; it is intended to be safer to inspect/share than raw IDs, but the overall identity directory should still be treated as sensitive.

## Matching rule (initial)
Two records are treated as the same person only if BOTH first name and last name match after normalization.

Normalization:
- trim
- collapse whitespace
- casefold

Name parsing:
- `"First Last"` → first token + last token
- `"Last, First"` → token before comma + first token after comma
- Middle names/initials are ignored for now (by construction).

## Provenance / append-only behavior
Observed external IDs and source references are appended to `aliases.json` with a stable `alias_key` to avoid re-adding identical observations on re-run.

## PersonLink registry
`person_links.json` records explicit links between external identifiers and canonical people:
- `system_fingerprint`: `sha256(<system>)`
- `source_patient_id`: `sha256(<system>:<value>)`
- `person_key`: canonical person UUID
- `verification_state`: `verified` | `unverified` | `user_confirmed`

### Review / confirm workflow (CLI)

List unverified links (share-safe output; no names/DOBs):

```bash
healthdelta identity review
```

Each line begins with a `link_id` (sha256 of `<system_fingerprint>:<source_patient_id>`). Confirm a link:

```bash
healthdelta identity confirm --link <link_id>
```

Link creation rules (MVP):
- If the external ID fingerprint is already linked, reuse that `person_key`.
- Otherwise, if the normalized name is unambiguous within the current run and matches exactly one existing person, create an `unverified` link.
- If ambiguity exists (e.g., multiple same-name patients in the same run, or multiple existing candidates), create a new `person_key` (no auto-merge).
