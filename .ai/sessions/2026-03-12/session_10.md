Issue: #240
Date: 2026-03-12

Summary
- Started a home-screen cleanup pass to remove operational/debug-style information from the main iPhone experience and keep the focus on health meaning first.

Work log
- Opened GitHub issue #240 using the required template.
- Reviewed the current `ContentView` composition after the `Combined / Fitness / Clinical` split.
- Identified remaining landing-page clutter: scope controls, data-scope details, connection settings copy, and completed operational status lines.
- Moved patient/window scope and sync metadata into a secondary `Care Context` sheet.
- Simplified the landing page to lead with the care domain selector, overview, primary trend, notes, and the three core actions.
- Removed completed operational status text from the main overview card so the first screen stays centered on health meaning rather than sync/debug detail.
- Updated the iOS export runbook to document the intentionally health-centered opening screen and secondary placement of operational controls.

Verification
- Synced the updated iOS sources to the MacBook Air workspace.
- Ran `xcodebuild test -project HealthDelta.xcodeproj -scheme HealthDelta -destination "platform=iOS Simulator,name=iPhone 17"` on the MacBook Air.
- Result: `69` tests passed, `0` failures.
