# Architecture (Draft)

## Goal
HealthDelta bootstraps once from an Apple Health `export.zip`, then continues incrementally via HealthKit anchored queries.

## Constraints
- Multi-person safe by default (inpatient scenarios).
- Identity resolution is safety-critical; never auto-merge ambiguous identities.
- Exports are append-only NDJSON, partitioned and privacy-safe (no names/IDs).

## Open Questions
- TODO: define minimal vertical slice end-to-end (bootstrap → NDJSON → ingest).

