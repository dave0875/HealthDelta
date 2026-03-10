Issue: #215

Title: iOS: stabilize on-device launch after install on physical iPhone

Source of truth
- GitHub issue #215

Scope
- Diagnose and fix the immediate on-device termination after successful install/launch on a connected physical iPhone.
- Establish concrete proof that the app starts without dyld failing to load `HealthDelta.debug.dylib`.

Constraints
- Preserve local signing credentials and provisioning details outside the repo.
- Do not commit personal Apple team or provisioning identifiers unless a follow-up issue explicitly requires it.
- Keep repo changes minimal and focused on deterministic device launch stability.

Acceptance focus
- No dyld startup failure for `HealthDelta.debug.dylib` on physical-device launch.
- Device launch proof shows the app remains alive past initial startup or presents expected UI.
- Generated iOS project/build configuration no longer relies on an invalidly signed debug dylib for device startup.
