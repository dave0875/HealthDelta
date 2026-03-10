# Session 43 - 2026-03-09

Issue: #216

Goal
- Wire the first manual on-device iOS export flow so the dashboard can populate local sync state.

Plan
- Add the required issue audit artifacts for #216 before changing tracked files.
- Define test seams around HealthKit authorization and export orchestration.
- Add failing iOS unit tests for dashboard/export behavior first.
- Implement the smallest app-side export path and refresh/error handling needed to satisfy the issue.
- Update the iOS export runbook to describe how the new manual flow is triggered.
- Rebuild and verify on the Mac/iPhone after unit tests pass.
