# Session 15 - 2026-03-08

Issue: #182

Goal
- Include hospital-record coverage evidence artifacts in share bundles.

Notes
- Confirmed there was no existing prompt/session history for Issue #182.
- Coverage report artifacts already live under `reports/`; the missing share-bundle path is `clinical_inventory.json`.
- Starting with share-bundle tests that require `coverage.json`, `coverage.md`, and `clinical_inventory.json` to be archived and manifested, including the zero-count case.
- Added `profile/` to the share-bundle allowlist so `clinical_inventory.json` can ship alongside the report coverage artifacts.
- Updated the share-bundle runbook to document the included hospital-record evidence artifacts.

Local verification
- `TZ=UTC python3 -m unittest tests/test_share_bundle.py -v`
