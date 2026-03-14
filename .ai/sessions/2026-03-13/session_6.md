Issue: #246

Summary
- Opened a narrow issue for the iPhone app freezing on load/refresh.
- Traced the startup path through `ContentView` and `DashboardViewModel`.
- Identified a strong freeze candidate: `SyncStatusStore.loadLatest()` synchronously scans large NDJSON files on the main actor to derive the delta window.

Planned Fix
- Stop deriving the delta window by reparsing NDJSON during launch.
- Persist `delta_start` and `delta_end` into the local run manifest during export.
- Make `SyncStatusStore` read those manifest fields directly so startup stays responsive even for large runs.
