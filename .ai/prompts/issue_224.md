Issue: #224

Title: Display iPhone dashboard times in local timezone

GitHub Issue URL: https://github.com/dave0875/HealthDelta/issues/224

Prompt
- Update the iPhone app so user-facing time values render in the device's local timezone instead of UTC.
- Keep stored manifest and NDJSON timestamps canonical; this is a display-only change.
- Cover the sync dashboard, sync details screen, and local insight freshness labels.
- Add deterministic iOS tests for the local-time formatting behavior and keep the Xcode simulator suite green.
