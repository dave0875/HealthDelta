Issue: #228

Follow-up Prompt 1

This follow-up does NOT change issue scope or acceptance criteria.

- The live phone still uploaded a manifest-only stub run after the first `#228` repair landed.
- Tighten the same issue so the upload action re-resolves the latest complete local run at upload time instead of relying on a potentially stale in-memory snapshot.
- Keep the fix constrained to the iOS upload path and add focused coverage that proves a stale displayed run ID cannot be uploaded when a newer complete run is available.
