---
Story
As an iOS user,
I want incremental HealthKit exports that use anchors correctly,
So that exports are fast and only include new data.

Context / Why
Incremental export is required to avoid full re-exports. Anchors must be persisted and replayed deterministically to prevent duplication or missed records.

Acceptance Criteria
- Given a prior export run, when the next run executes, then the anchored query only returns records after the persisted anchor and writes deterministic NDJSON output.
- Given no new records, when the incremental export runs, then it produces a deterministic no-op and preserves the anchor.
- Given this change, when `ci.yml` job `ios-xcode-tests` runs, then it passes and uploads `ios-xcresult`.
- Given this change, when `ci.yml` job `linux-tests` runs, then it passes if any shared Python code is touched.

Out of Scope
- Backend ingestion or server-side processing of incremental exports.

Notes
- Deployment proof not required unless deployable artifacts are changed.
---
