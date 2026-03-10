# Session 45 - 2026-03-09

Issue: #216

Goal
- Fix the missing HealthKit entitlement in the first manual iOS export flow.

Notes
- After adding `NSHealthShareUsageDescription`, the app no longer dies on the missing privacy string.
- The next on-device retry now reaches the app-level export error state: `Unable to export HealthKit data. Missing com.apple.developer.healthkit entitlement`.
- The minimal tracked fix is to add a signed entitlement file containing `com.apple.developer.healthkit` and wire it through the generated Xcode project so the app binary is signed with the HealthKit entitlement on device.
