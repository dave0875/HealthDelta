Issue #244: Deploy ORIN backend from the latest tagged release image

URL: https://github.com/dave0875/HealthDelta/issues/244

Story
As a HealthDelta operator,
I want the ORIN backend container updated to the latest tagged release image,
So that live insights use the merged strong-label wellness processing instead of an ad hoc older runtime.

Context / Why
ORIN is currently running an ad hoc backend image rather than the latest tagged release. The repo-side fix for strong wellness labels is merged and green, but the live container will not reflect it until the backend is rebuilt, released, and deployed from the standard release pipeline.

Acceptance Criteria
- Given the latest green main commit, when a new backend release tag is cut, then Release builds the CLI/package artifacts and GHCR backend image for that tag successfully.
- Given the released backend image, when the ORIN backend deploy workflow runs, then ORIN serves the tagged backend image rather than the ad hoc issue image.
- Given the updated ORIN backend, when querying `/version` and live insight endpoints, then the runtime reports the expected version/tag lineage and serves the live dataset successfully.
- CI, Release, and Deploy proof are all green and persisted.

Out of Scope
- Additional code changes beyond deployment/versioning needed to ship the already-merged backend logic.
- iPhone UI changes.
- Reprocessing data beyond what the deployed backend already serves.

Notes
- Prefer the existing tagged release and ORIN deploy workflows.
- Remove or supersede the ad hoc ORIN backend container path with the standard tagged image.
