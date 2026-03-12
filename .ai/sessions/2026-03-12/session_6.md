# Session 6

- Date: 2026-03-12
- Issue: #236
- Goal: Make the iPhone dashboard use ORIN-backed patient scope options and show overview progress only for real active work.

Actions
- Confirmed from live ORIN logs that `/insights/current` completed successfully for the phone, so the long-lived overview spinner is not waiting on the backend.
- Confirmed the current patient scope UI only builds options from the local canonical person ID plus manual override, which explains why live ORIN patient buckets are not shown.
- Opened Issue `#236` to justify the scope and progress-state fixes before changing app or backend code.
- Added a new authenticated backend endpoint `GET /patients/current` that derives deterministic share-safe patient scope options from the current dataset analysis artifacts.
- Added a new iPhone `ORINPatientScopeService` and updated the dashboard refresh flow so remote patient scope options are loaded alongside ORIN insights.
- Updated the patient scope card to merge:
  - `All patients`
  - the known local iPhone record
  - live ORIN patient buckets
  - manual canonical-person overrides as a fallback
- Updated the overview card state model so the spinner is shown only while export/upload/refresh work is active, while completed upload status is rendered as plain text.
- Updated iOS and ORIN runbooks to document the new patient-scope endpoint and the corrected overview progress behavior.
- Hot-patched the live ORIN backend container so `/patients/current` is available immediately.
- Built, installed, and launched the updated iPhone app on device `00008130-000971690021401C`.

Notes
- The rebuilt Apple-export dataset on ORIN currently has three patient buckets in `coverage_by_person.csv`, so the app needs a live remote scope source rather than only device-local state.

Verification
- Local backend verification passed:
  - `TZ=UTC .venv/bin/python -m unittest tests.test_backend_insights_api -v`
- Focused iOS simulator verification passed on the MacBook Air:
  - `xcodebuild test -project HealthDelta.xcodeproj -scheme HealthDelta -only-testing:HealthDeltaTests/DashboardViewModelTests -only-testing:HealthDeltaTests/ORINInsightsServiceTests -only-testing:HealthDeltaTests/ORINPatientScopeServiceTests -destination "platform=iOS Simulator,name=iPhone 17"`
  - Result: `26` tests passed, `0` failures.
- Live ORIN verification passed:
  - `GET /patients/current` returns three share-safe patient buckets for the rebuilt Apple-export dataset.
- Device deployment verification passed:
  - build succeeded on the MacBook Air
  - app installed to `00008130-000971690021401C`
  - app launched and remained visible in `devicectl` process output
