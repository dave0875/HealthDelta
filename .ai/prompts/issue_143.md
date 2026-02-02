---
Story
As an operator,
I want ORIN tag-triggered deploy to wait for image availability,
So that deploy does not fail when release image publish and deploy workflows start concurrently.

Context / Why
On tag v0.0.4, Deploy Backend (ORIN) started before GHCR tag was visible and failed with `manifest unknown`. The deploy workflow should handle publish latency by polling for tag availability before compose pull.

Acceptance Criteria
- Given tag-triggered deploy, when GHCR image publish lags briefly, then deploy waits/polls until the tag is available (bounded timeout) instead of failing immediately.
- Workflow logs clearly show wait attempts and timeout behavior.
- Automatic tag-triggered deploy succeeds after release publish in normal conditions.

Out of Scope
- Changing release tagging strategy.
- Backend feature changes.

Notes
- Keep polling bounded and deterministic.
---
