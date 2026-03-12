# Session 18

- Date: 2026-03-11
- Issue: #231
- Goal: Replay the saved iPhone full export and later incremental runs from the MacBook Air into live ORIN so the deployed cumulative dataset reflects the full available history.

Actions
- Opened an operational backfill issue because the cumulative upload behavior is deployed but live ORIN current still points at the earlier five-row delta dataset.
- Scoped the work to replay the saved MacBook Air export directories oldest-to-newest through the live ORIN upload API without changing repo code.
- Planned to verify the resulting live dataset through `/datasets/current`, the current export manifest, and `/insights/current`.
- Inspected the MacBook Air and confirmed the copied export baseline existed at `~/HealthDelta/ios_exports/run_20260310_020742` with `232,236` observations and a `75.6 MB` NDJSON file.
- Inspected the connected iPhone app container through `xcrun devicectl` and identified the full replay set: `run_20260310_020742`, `run_20260310_133320`, `run_20260311_000618`, and `run_20260311_151707`; later directories on the phone were manifest-only stubs with no observations file.
- Copied the complete run directories from the phone to `~/HealthDelta/replay_exports` on the MacBook Air and replayed those four runs oldest-to-newest into live ORIN through `POST /upload-sessions`, `PUT /upload-sessions/{id}/chunks/0`, and `POST /upload-sessions/{id}/finalize`.
- Verified the live ORIN current dataset moved from the pre-fix five-row delta to a cumulative `run_orin_cumulative_current` export with preserved `source_runs` provenance for all four replayed uploads.
- Verified live `/insights/current` returned `status=ok` and two cards against the cumulative current dataset.

Verification
- Live replay result:
  - `run_20260310_020742` -> `dataset_20260312T034201Z_9c1f19`
  - `run_20260310_133320` -> `dataset_20260312T034208Z_61ec1b`
  - `run_20260311_000618` -> `dataset_20260312T034214Z_c33bef`
  - `run_20260311_151707` -> `dataset_20260312T034220Z_4132a6`
- Live `/datasets/current` after replay:
  - dataset `dataset_20260312T034220Z_4132a6`
  - `export.zip` size `13,792,887` bytes
  - manifest `run_id=run_orin_cumulative_current`
  - `row_counts.observations=230383`
  - `source_runs` contains all four replayed run IDs
- Live `/insights/current` after replay:
  - `status=ok`
  - cards `Doctor's Note`, `Summary`
