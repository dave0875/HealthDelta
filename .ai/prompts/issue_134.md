---
Story
As an operator,
I want release backend container images published as native multi-arch manifests,
So that ORIN (ARM64) and x86 hosts can pull the same release tag without emulation.

Context / Why
Current backend release images are amd64-only, which leaves ORIN deployment as a platform risk. Multi-arch publishing closes this cap while preserving existing release semantics.

Acceptance Criteria
- Given a tag release workflow run, when backend image publish executes, then GHCR tag contains linux/amd64 and linux/arm64 in one manifest.
- Release workflow logs include `docker buildx imagetools inspect` output showing both architectures.
- Existing CLI artifact publication and release behavior remain unchanged.
- Workflow verification remains deterministic and share-safe.

Out of Scope
- ORIN deployment execution.
- Application feature changes.

Notes
- Keep image tags/versioning consistent with existing release flow.
---
