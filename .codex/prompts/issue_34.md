Issue: https://github.com/dave0875/HealthDelta/issues/34

Scope / intent (immutable)
- Add a persisted, single-user `canonical_person_id` (UUIDv4) for the iOS incremental exporter.
- Ensure every iOS NDJSON row includes `canonical_person_id` without deriving from PII/device identifiers.

Acceptance criteria (restated)
- Provide a small iOS module that persists a UUIDv4 `canonical_person_id` in the app sandbox.
- Update `IncrementalNDJSONExporter` to include `canonical_person_id` on every emitted NDJSON row.
- Unit tests verify:
  - `canonical_person_id` is stable across loads
  - `canonical_person_id` parses as a UUID string
  - exported NDJSON rows contain `canonical_person_id`
- Record audit artifacts (prompt/session/review/TIME.csv) and close with green CI (macOS `ios-xcresult` artifact).

Design notes
- Persist ID as a newline-terminated UUID string in the app sandbox (Documents).
- Keep deterministic tests by injecting a fixed `canonical_person_id` provider into the exporter.
- Do not log any PHI/PII; do not derive IDs from names, DOB, or device identifiers.

Plan
1) Add `CanonicalPersonIDStore` (file-backed; atomic write) under `ios/HealthDelta/Sources/`.
2) Add tests for store stability/UUID validity under `ios/HealthDelta/Tests/`.
3) Update `IncrementalNDJSONExporter` to accept an injected `canonicalPersonIDProvider` and to include `canonical_person_id` in emitted rows.
4) Update exporter tests to assert row contains `canonical_person_id` and preserve byte-stable behavior across reruns by using a fixed ID provider.
5) CI proof: verify macOS job uploads `ios-xcresult`; comment evidence; close issue.

Constraints
- Repo mutations on Ubuntu host `GORF` only; Xcode execution only via GitHub Actions self-hosted macOS runner.
- Synthetic-only test data.

