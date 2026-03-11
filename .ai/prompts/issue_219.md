Issue: #219

Title: Add first direct iPhone to ORIN upload path for iOS export runs

Source of truth
- GitHub issue #219

Scope
- Add a first user-triggered direct upload path from the iOS app to ORIN for completed iOS export runs.
- Reuse existing backend/upload-plane capabilities where practical and keep the change minimal.

Constraints
- Preserve the existing local export path and Mac-assisted fallback path.
- Keep the first version explicit and operator-driven rather than background/automatic.
- Prefer deterministic handling of a completed run directory over streaming partial export state.

Acceptance focus
- A completed iOS run can be uploaded directly to a configured ORIN endpoint from the app.
- Upload success/failure is observable in the app.
- ORIN persists the uploaded run in the expected server-side location.
- Relevant iOS and Python tests pass and docs describe the path accurately.
