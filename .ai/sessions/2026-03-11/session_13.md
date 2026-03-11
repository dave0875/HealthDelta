# Session 13

- Date: 2026-03-11
- Issue: #228
- Goal: Finish the iPhone-side repair so uploads use a complete run directory and preserve valid run-relative archive entries for ORIN.

Actions
- Confirmed the first `#228` path fix was insufficient on-device because current uploads still produced malformed zip names and the app was selecting a newer manifest-only stub run.
- Reworked the archive builder to enumerate run-directory subpaths directly so ZIP entries are always emitted as `run_id/<relative path>` without `/private` path leakage.
- Tightened `SyncStatusStore` so `loadLatest()` skips incomplete run directories whose manifest has no NDJSON files, preventing the app from uploading stub exports that ORIN cannot analyze.
