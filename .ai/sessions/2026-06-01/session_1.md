# Session 1 - DashboardViewModel patient-scope test isolation

Date: 2026-06-01
Issue: #254

## Summary
- Investigated macOS Xcode CI run `26786904590`.
- Confirmed the first attempt lost runner communication during `xcodebuild`.
- Reran the macOS job after the runner returned online and downloaded the uploaded `ios-xcresult` artifact.
- Found repeated test-launch restart boundaries and an unintended request to `http://orin.local:8080/patients/current`.
- Added fake patient-scope fetchers to the successful upload and dashboard-refresh fixtures that exercise patient-scope refreshes.

## Verification
- Red evidence: `xcodebuild` exit `65` in macOS job `78966444764`.
- `git diff --check`: passed.
- Authoritative macOS CI rerun: pending.
