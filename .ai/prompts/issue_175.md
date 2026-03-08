---
Story
As an operator,
I want the pipeline to produce a verified share-safe bundle in one flow,
So that collaboration artifacts are consistent and validated.

Context / Why
Share bundles exist, but operators still need a cohesive pipeline flow that validates NDJSON outputs and verifies bundle contents. Without this, share safety can regress.

Acceptance Criteria
- Given a share-mode run, when the operator triggers bundle creation, then `healthdelta share bundle` emits a deterministic tarball with a manifest and `healthdelta share verify` passes.
- Given NDJSON outputs, when `healthdelta export validate` runs as part of the flow, then validation artifacts are included in the share bundle.
- Given this change, when `ci.yml` job `linux-tests` runs, then it passes.

Out of Scope
- Any handling of non-share-safe (PII/PHI) datasets.

Notes
- Deployment proof not required unless deployable artifacts are changed.
---
