# Session 14

- Date: 2026-03-11
- Issue: #228
- Goal: Eliminate the last stale-run path so iPhone uploads always use the newest complete local export.

Actions
- Verified on the live device that the rebuilt app still uploaded `run_20260311_183958`, proving the archive fix alone was insufficient because the upload path could still trust a stale in-memory sync snapshot.
- Scoped the follow-up to a small view-model hardening change: reload the latest complete run immediately before upload and update the displayed snapshot from that fresh resolution.
- Added focused regression coverage so the upload action cannot send an older cached run ID when a newer complete run is available.
