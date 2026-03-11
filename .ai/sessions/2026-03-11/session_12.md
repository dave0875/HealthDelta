# Session 12

- Date: 2026-03-11
- Issue: #228
- Goal: Fix malformed iPhone upload archive paths so ORIN can read uploaded run artifacts.

Actions
- Inspected the live ORIN datasets and confirmed both uploaded iPhone archives contained malformed zip entry paths like `run_id//privatemanifest.json`.
- Traced the bug to the iOS upload archive builder using raw string replacement against `runDirectory.path` to derive relative archive paths.
- Scoped the fix to a robust run-relative path derivation that tolerates `/private/...` versus `/var/...` path differences and added a targeted regression test for that mismatch.
