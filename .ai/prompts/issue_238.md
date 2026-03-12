# Issue #238 Prompt

Issue: #238
Title: Local-only patient naming on iPhone without Patient N fallbacks

Immutable execution prompt recorded at start of work.

Scope
- Replace painful generic patient names on iPhone with a durable local-only naming layer.
- Seed the local iPhone record label from device-local context when possible.
- Present an on-device patient-labeling flow for ORIN patient buckets that do not yet have local labels.

Goals
- Stop surfacing `Patient 1`, `Patient 2`, and `Unresolved records` as the primary patient names in the iPhone scope selector.
- Keep all human-readable patient names local to the device only.
- Preserve ORIN's share-safe API contract while improving the bedside-manner of the app.

Constraints
- No secrets or PII in `.ai/`.
- Do not send local patient labels to ORIN or include them in exports.
- Add iOS unit coverage for label suggestion and patient option rendering.
