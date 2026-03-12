Issue: #239
Date: 2026-03-12

Summary
- Started implementation for a bedside-friendly Combined / Fitness / Clinical split in the iPhone dashboard.
- Plan is to add deterministic domain tagging to insight payloads and then reorganize the iOS UI around those domains with explicit empty states and permission language.

Work log
- Opened GitHub issue #239 using the required template.
- Inspected current dashboard, insight model, backend insight payloads, and iOS HealthKit export coverage.
- Identified that the current dashboard blends all domains together and that current insight payloads do not carry an explicit domain field.
- Added deterministic domain tagging to ORIN insight cards and extended the iPhone insight model to carry `combined`, `fitness`, and `clinical`.
- Reworked the iPhone `Clinical Compass` dashboard to expose bedside-friendly `Combined`, `Fitness`, and `Clinical` sections with explicit clinical empty states and Apple Health permission language.
- Updated the iOS export runbook to document the domain split and current permission boundary.

Verification
- `TZ=UTC .venv/bin/python -m unittest tests.test_backend_insights_api -v`
- `xcodebuild test -project HealthDelta.xcodeproj -scheme HealthDelta -destination "platform=iOS Simulator,name=iPhone 17"`
