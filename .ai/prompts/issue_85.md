---
Story
As an operator,
I want a single share-safe artifact bundle that proves hospital record ingestion,
So that I can share evidence without exposing PII.

Context / Why
The mission requires shareable, auditable outputs.

Acceptance Criteria
- Bundle includes NDJSON, DuckDB, reports, Doctor’s Note, and validation logs.
- Share-verify passes and records a deterministic manifest.
- Tests assert required files and hashes.

Out of Scope
- UI distribution.
---
