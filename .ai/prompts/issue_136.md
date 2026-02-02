---
Story
As an operator,
I want a reproducible GitHub->ORIN deployment proof using a real release tag,
So that backend container deployment capability is demonstrated end-to-end with evidence artifacts.

Context / Why
After enabling runner diagnostics and multi-arch publish, the remaining cap is a full tagged release flowing through ORIN deploy verification with logs/artifacts.

Acceptance Criteria
- Given a new release tag, when Release workflow runs, then backend multi-arch image is published and inspect logs show `linux/amd64` and `linux/arm64`.
- Given that tag, when Deploy Backend (ORIN) runs, then ORIN pulls/deploys the tagged image and backend verification passes (`/healthz`, `/version` version+sha match).
- Deploy workflow uploads deterministic artifacts containing deploy and verify logs.
- Issue closure references run URLs for diagnostics, release, and deploy proof.

Out of Scope
- Feature-level backend changes.
- New governance policy requirements.

Notes
- If ORIN runner/host prerequisites are unavailable, preserve repo-side fixes and document exact host remediation required.
---
