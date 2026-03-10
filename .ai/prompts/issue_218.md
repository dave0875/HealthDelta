Issue: #218

Title: Strengthen iOS observation identity to avoid false duplicate collapse

Source of truth
- GitHub issue #218

Scope
- Strengthen the iOS HealthKit observation export identity so distinct samples do not collapse to the same `record_key`.
- Keep the change focused on the iOS incremental export contract and the downstream loader/tests/docs that consume it.

Constraints
- Preserve backward compatibility for already-exported iOS runs where practical.
- Do not broaden this into a full identity redesign for non-iOS NDJSON streams.
- Prefer using stable HealthKit-native identity rather than inventing a downstream-only compound key.

Acceptance focus
- Exported iOS rows include a stronger sample identity field.
- `record_key` for iOS rows is derived from stable source identity rather than only visible value/time fields.
- Distinct samples with identical visible values/times produce different keys.
- Relevant iOS and Python tests pass in CI and docs describe the contract accurately.
