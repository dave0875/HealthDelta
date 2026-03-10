Issue: #216

Title: iOS: wire first on-device export flow

Source of truth
- GitHub issue #216

Scope
- Add the first user-facing iOS export path so a person running the app on an iPhone can trigger a HealthKit export and populate local dashboard data.
- Keep the change minimal and focused on the current iOS skeleton, which exports observations/manifests into the app sandbox.

Constraints
- Preserve existing app-local storage layout under `Documents/HealthDelta/<run_id>/`.
- Keep ORIN/backend integration out of scope.
- Prefer small protocol seams so export orchestration and failure handling are unit-testable.

Acceptance focus
- The app exposes a manual export action.
- Manual export requests HealthKit authorization as needed and runs the existing incremental exporter.
- Success refreshes the dashboard from local run artifacts.
- Failure or denied access surfaces an observable error state.
- Deterministic iOS tests cover the new orchestration behavior.
