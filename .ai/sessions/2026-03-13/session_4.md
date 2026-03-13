# Session 4 - Issue #244

Date: 2026-03-13
Issue: #244 - Deploy ORIN backend from the latest tagged release image

Goals
- Move ORIN off the ad hoc backend image onto the standard tagged release path.
- Cut a release tag from the current green main commit.
- Verify Release, Deploy, and live ORIN runtime/version behavior.

Progress
- Opened Issue #244 with the required template.
- Confirmed ORIN is currently running `healthdelta-backend:issue230-live` rather than a tagged GHCR image.
- Pushed audit artifacts to `main` and waited for branch CI to pass on commit `2da48224d408f6a033e0f07fc4a83aeadc29f7ef`.
- Cut and pushed release tag `v0.0.8`.
- Confirmed Release built the GHCR backend image and GitHub Release successfully.
- Remediated ORIN host deploy blockers:
  - fixed `/opt/healthdelta/data` ownership and writeability for the `ghrunner` deploy path
  - fixed `/opt/healthdelta/compose.yaml` ownership so the deploy workflow could overwrite managed files
  - removed the stale ad hoc `healthdelta-backend-1` container so compose could recreate the service
- Reran the ORIN deploy workflow until it passed.
- Restored the live ORIN env after deploy so upload token, Ollama settings, and LAN bind host remained configured while keeping the newly deployed `v0.0.8` image.

Verification
- Release run `23066260326` passed for `v0.0.8`.
- Deploy Backend (ORIN) run `23066260323` passed after host-side remediation.
- Live ORIN checks after deploy:
  - `/healthz` -> `{\"ok\": true}`
  - `/version` -> version `0.0.8`, git sha `2da48224d408f6a033e0f07fc4a83aeadc29f7ef`
  - `/datasets/current` -> live dataset `dataset_20260312T155255Z_apple_bootstrap`
  - `/insights/current?window_days=30` -> `status: ok`

Residual note
- `/patients/current` still returns `500 patient_scope_failed` on the current Apple bootstrap dataset under the deployed runtime. That defect predates this deployment issue and was not part of the container-update acceptance criteria.
