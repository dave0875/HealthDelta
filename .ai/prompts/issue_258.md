Issue: #258
Title: Ops: realign mail server HealthDelta deployment to latest release tag

Objective
- Replace the ad hoc `issue247-live` image tag on the `mail` host with the latest release-style HealthDelta tag.
- Preserve the host's existing runtime settings while restoring auditable release lineage at `/version`.

Acceptance anchors
- A latest release-style tag exists and is available as a GitHub Release.
- The `mail` host pins `HEALTHDELTA_BACKEND_IMAGE_TAG` to that release tag instead of an `issue*-live` tag.
- The live backend remains healthy and reports the expected release version lineage after redeploy.
- This work session is recorded in repo audit artifacts.
